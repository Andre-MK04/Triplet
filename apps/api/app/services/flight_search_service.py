import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.db.repositories.cached_deals_repository import CachedDealsRepository
from app.db.repositories.price_observations_repository import PriceObservationsRepository
from app.models import Flight, ProviderMetadata, TripSearchRequest
from app.providers import DatabaseFlightProvider, FlightProvider
from app.providers.errors import ProviderError
from app.providers.flight_provider import DateRange
from app.providers.registry import UnknownFlightProviderError, build_live_provider, build_provider

logger = logging.getLogger(__name__)


class FlightProviderNotImplementedError(NotImplementedError):
    pass


@dataclass
class FlightSearchResult:
    flights: list[Flight]
    metadata: ProviderMetadata


class FlightSearchService:
    def __init__(
        self,
        db: Session | None = None,
        provider_name: str | None = None,
        provider: FlightProvider | None = None,
    ):
        self.provider_name = (provider_name or settings.flight_provider).lower()
        self.db = db
        self.provider = provider or self._build_provider(db)

    def search_candidate_flights(self, request: TripSearchRequest) -> list[Flight]:
        return self.search_candidate_flights_with_metadata(request).flights

    def search_candidate_flights_with_metadata(self, request: TripSearchRequest) -> FlightSearchResult:
        if self.provider_name == "hybrid":
            result = self._search_hybrid(request)
        else:
            flights = self._search_with_provider(self.provider, request)
            metadata = self._metadata_from_provider(self.provider, provider_used=self.provider_name)
            metadata.liveProviderSucceeded = metadata.liveProviderAttempted and bool(flights)
            result = FlightSearchResult(flights=flights, metadata=metadata)

        self._record_price_observations(result.flights)
        logger.info(
            "flight_search provider=%s flights=%s live_attempted=%s cached=%s",
            result.metadata.providerUsed,
            len(result.flights),
            result.metadata.liveProviderAttempted,
            result.metadata.cachedResultsUsed,
        )
        return result

    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
    ) -> list[Flight]:
        return self.provider.search_flights(origin_codes, start_date, end_date, destination_codes)

    def discover_round_trip_fares(self, request: TripSearchRequest):
        """Round-trip fares, served from the deals cache when fresh.

        Open "anywhere" searches read the scheduled deals cache and only call the
        provider (city-directions) on a cold/stale cache, then warm it. A specific
        requested destination always does a direct per-route round-trip query (so
        that place yields something) and caches the result. Read-through keeps the
        user path off the live API on the common path.
        """
        provider = self.provider
        if self.provider_name == "hybrid":
            if self.db is None:
                return []
            try:
                provider = build_live_provider(self.db)
            except (UnknownFlightProviderError, ProviderError):
                return []

        deals_repo = CachedDealsRepository(self.db) if self.db is not None else None
        try:
            if request.destinationAirports:
                routes = getattr(provider, "round_trips_for", None)
                if not callable(routes):
                    return []
                fares = routes(
                    request.originAirports,
                    request.destinationAirports,
                    DateRange(start=request.startDate, end=request.endDate),
                )
                if deals_repo and fares:
                    deals_repo.upsert_deals(fares)
                return fares

            # "Anywhere": serve fresh cached deals; only fetch live on a cold cache.
            if deals_repo and deals_repo.has_fresh(request.originAirports):
                return deals_repo.fresh_deals(request.originAirports)
            discover = getattr(provider, "discover_round_trips", None)
            if not callable(discover):
                return []
            fares = discover(request.originAirports)
            if deals_repo and fares:
                deals_repo.upsert_deals(fares)
            return fares
        except ProviderError:
            return []

    def _build_provider(self, db: Session | None) -> FlightProvider:
        if self.provider_name == "hybrid":
            if db is None:
                raise UnknownFlightProviderError("Hybrid flight provider requires a database session.")
            return DatabaseFlightProvider(db)
        return build_provider(self.provider_name, db)

    def _search_hybrid(self, request: TripSearchRequest) -> FlightSearchResult:
        if self.db is None:
            raise UnknownFlightProviderError("Hybrid flight provider requires a database session.")

        database_provider = DatabaseFlightProvider(self.db)
        cached_flights = self._search_with_provider(database_provider, request)

        # Read-through fast path: for an "anywhere" search whose origins already
        # have fresh cached deals, serve from the database and skip the live
        # provider entirely. The scheduled tick (and cold searches) keep the
        # cache warm. Specific-destination searches always go live (rarer, and
        # we want that exact place fresh).
        if not request.destinationAirports and CachedDealsRepository(self.db).has_fresh(request.originAirports):
            metadata = ProviderMetadata(
                providerUsed="database",
                providerName="database",
                cachedResultsUsed=True,
            )
            return FlightSearchResult(flights=cached_flights, metadata=metadata)

        try:
            live_provider = build_live_provider(self.db)
            live_flights = self._search_with_provider(live_provider, request)
        except ProviderError as exc:
            logger.warning(
                "hybrid_fallback live_provider=%s reason=%s cached_flights=%s",
                settings.live_flight_provider,
                type(exc).__name__,
                len(cached_flights),
            )
            return FlightSearchResult(
                flights=cached_flights,
                metadata=ProviderMetadata(
                    providerUsed="database",
                    providerName=settings.live_flight_provider,
                    liveProviderAttempted=True,
                    liveProviderSucceeded=False,
                    cachedResultsUsed=True,
                    providerWarnings=[
                        f"Using cached/database fares because {settings.live_flight_provider} was unavailable: {exc}"
                    ],
                ),
            )

        merged = deduplicate_flights(cached_flights + live_flights)
        metadata = self._metadata_from_provider(live_provider, provider_used="hybrid")
        metadata.liveProviderAttempted = True
        metadata.liveProviderSucceeded = bool(live_flights)
        metadata.cachedResultsUsed = bool(cached_flights)
        return FlightSearchResult(flights=merged, metadata=metadata)

    def _search_with_provider(self, provider: FlightProvider, request: TripSearchRequest) -> list[Flight]:
        return_window_end = request.endDate + timedelta(days=request.maxTripLengthDays)
        if request.destinationAirports:
            # Targeted search: origins → chosen destinations, returns from those
            # destinations back to the origins. Live providers spend their request
            # budget on exactly the routes the user asked for.
            outbound_flights = provider.search_flights(
                request.originAirports,
                request.startDate,
                request.endDate,
                destination_codes=request.destinationAirports,
                direct_only=request.directOnly,
            )
            return_flights = provider.search_flights(
                request.destinationAirports,
                request.startDate,
                return_window_end,
                destination_codes=request.originAirports,
                direct_only=request.directOnly,
            )
        else:
            outbound_flights = provider.search_outbound_flights(
                request.originAirports,
                request.startDate,
                request.endDate,
                request.directOnly,
            )
            return_flights = provider.search_return_flights(
                request.originAirports,
                request.startDate,
                return_window_end,
                request.directOnly,
            )
        return deduplicate_flights(outbound_flights + return_flights)

    def _metadata_from_provider(self, provider: FlightProvider, provider_used: str) -> ProviderMetadata:
        is_live_provider = provider.name not in {"database", "mock"}
        return ProviderMetadata(
            providerUsed=provider_used,
            providerName=provider.name,
            liveProviderAttempted=is_live_provider,
            cachedResultsUsed=provider.name == "database",
            requestsAttempted=provider.requests_attempted or None,
            requestsLimit=getattr(provider, "max_requests", None),
            rawOffersCount=provider.raw_offers_count or None,
            mappedFlightsCount=provider.mapped_flights_count or None,
            skippedOffersCount=provider.skipped_offers_count or None,
            deepLinksReturned=provider.deep_links_returned or None,
            affiliateLinksGenerated=provider.affiliate_links_generated or None,
            providerWarnings=list(dict.fromkeys(provider.warnings)),
        )

    def _record_price_observations(self, flights: list[Flight]) -> None:
        if not self.db or not flights:
            return
        try:
            recorded = PriceObservationsRepository(self.db).record_flights(flights)
            if recorded:
                logger.info("price_observations recorded=%s", recorded)
        except Exception:
            # Price history is best-effort; never fail a search over it.
            logger.exception("price_observation_recording_failed")


def deduplicate_flights(flights: list[Flight]) -> list[Flight]:
    confidence_rank = {"live": 3, "indicative": 2, "cached": 1, "mock": 0}
    by_key: dict[tuple, Flight] = {}
    for flight in flights:
        key = (
            flight.origin,
            flight.destination,
            flight.departureDateTime,
            flight.arrivalDateTime,
            flight.airline,
        )
        existing = by_key.get(key)
        if not existing:
            by_key[key] = flight
            continue
        new_rank = confidence_rank.get(flight.confidenceLevel, 0)
        old_rank = confidence_rank.get(existing.confidenceLevel, 0)
        if new_rank > old_rank or (new_rank == old_rank and flight.price < existing.price):
            by_key[key] = flight
    return list(by_key.values())
