import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.data.flight_places import canonical_code, is_flightable_place, place_matches_filters
from app.data.geography import scope_matches
from app.db.repositories.cached_deals_repository import CachedDealsRepository
from app.db.repositories.price_observations_repository import PriceObservationsRepository
from app.models import Flight, ProviderMetadata, TripSearchRequest
from app.providers import DatabaseFlightProvider, FlightProvider
from app.providers.errors import ProviderError
from app.providers.flight_provider import DateRange
from app.providers.registry import UnknownFlightProviderError, build_live_provider, build_provider
from app.services.destination_scope import DestinationScope, resolve_destination_scope

logger = logging.getLogger(__name__)

# Below this many in-window options, an "anywhere" search is not really answered
# by the cache and is worth a provider call for the dates actually requested.
ANYWHERE_MIN_RESULTS = 8


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
        cache_only: bool = False,
    ):
        self.provider_name = (provider_name or settings.flight_provider).lower()
        self.db = db
        self.cache_only = cache_only and self.provider_name in {"travelpayouts", "hybrid"}
        self.provider = provider or self._build_provider(db)
        self.deals_cache_used = False
        self.deals_provider_attempted = False
        self.deals_provider_succeeded = False
        self._scope: DestinationScope | None = None

    def search_candidate_flights(self, request: TripSearchRequest) -> list[Flight]:
        return self.search_candidate_flights_with_metadata(request).flights

    def search_candidate_flights_with_metadata(self, request: TripSearchRequest) -> FlightSearchResult:
        if self.cache_only:
            return FlightSearchResult(
                flights=[],
                metadata=ProviderMetadata(
                    providerUsed="database",
                    providerName="cached_deals",
                    cachedResultsUsed=True,
                ),
            )
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

    def resolve_scope(self, request: TripSearchRequest) -> DestinationScope:
        """Resolve (and memoise) what this request's destination fields mean."""
        if self._scope is None:
            hint: tuple[str, ...] = ()
            if self.db is not None:
                try:
                    hint = CachedDealsRepository(self.db).country_ranking(request.originAirports)
                except SQLAlchemyError:
                    logger.warning("country_ranking_failed", exc_info=True)
                    self.db.rollback()
            self._scope = resolve_destination_scope(
                request,
                ranked_country_hint=hint,
                request_budget=settings.travelpayouts_max_requests_per_search,
            )
        return self._scope

    def discover_round_trip_fares(self, request: TripSearchRequest):
        """Round-trip fares, served from the deals cache when fresh.

        Open "anywhere" searches read the scheduled deals cache and only call the
        provider (city-directions) on a cold/stale cache, then warm it. Any named
        destination — a city, a country, a region, a continent, or simply
        "outside Europe" — is resolved to concrete query targets and asked about
        directly, so a requested place yields fares whether or not the shared
        discovery cache already happened to cover it. Read-through keeps the user
        path off the live API on the common path.
        """
        provider = self.provider
        if self.provider_name == "hybrid":
            if self.db is None:
                return []
            try:
                provider = build_live_provider(self.db)
            except (UnknownFlightProviderError, ProviderError):
                return []

        scope = self.resolve_scope(request)
        deals_repo = CachedDealsRepository(self.db) if self.db is not None else None
        try:
            if self.cache_only:
                if not deals_repo:
                    return []
                self.deals_cache_used = True
                return self._filter_round_trip_fares(deals_repo.fresh_deals(request.originAirports), request)
            if scope.is_targeted:
                fares = self._targeted_round_trip_fares(provider, request, scope)
                if deals_repo and fares:
                    self._cache_deals(deals_repo, fares)
                self.deals_provider_succeeded = bool(fares)
                if deals_repo:
                    # A targeted scope can also be satisfied by deals we already
                    # hold, so fold the cache in rather than throwing it away.
                    cached = deals_repo.fresh_deals(request.originAirports)
                    if cached:
                        self.deals_cache_used = True
                        fares = fares + cached
                return self._filter_round_trip_fares(fares, request)

            # "Anywhere": serve fresh cached deals, then top up from the provider
            # only if they don't actually answer the question.
            cached: list = []
            if deals_repo and deals_repo.has_fresh(request.originAirports):
                self.deals_cache_used = True
                cached = self._filter_round_trip_fares(deals_repo.fresh_deals(request.originAirports), request)
                if len(cached) >= ANYWHERE_MIN_RESULTS:
                    return cached

            fares = self._open_round_trip_fares(provider, request, cold_cache=not cached)
            if deals_repo and fares:
                self._cache_deals(deals_repo, fares)
            self.deals_provider_succeeded = bool(fares)
            return cached + self._filter_round_trip_fares(fares, request)
        except ProviderError:
            return []

    def _open_round_trip_fares(self, provider, request: TripSearchRequest, cold_cache: bool):
        """Fares for an "anywhere" search.

        The shared discovery cache answers "cheapest from here, ever", which is
        great for warming but often lands outside the dates someone asked about.
        So an open search also asks for real fares inside its own date window,
        and only falls back to broad discovery when there is no cache to warm.
        """
        fares: list = []
        in_window = getattr(provider, "round_trips_in_window", None)
        if callable(in_window):
            self.deals_provider_attempted = True
            fares.extend(in_window(request.originAirports, DateRange(start=request.startDate, end=request.endDate)))

        discover = getattr(provider, "discover_round_trips", None)
        if cold_cache and callable(discover):
            self.deals_provider_attempted = True
            fares.extend(discover(request.originAirports))
        return fares

    def one_way_fares_for(
        self, request: TripSearchRequest, legs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], list]:
        """Per-date one-way fares for each hop of a chained itinerary.

        Multi-city and open-jaw trips are priced hop by hop, so each leg needs
        its own calendar of fares rather than a round-trip bundle. Returns {} when
        the provider cannot answer, which the caller reads as "this route could
        not be priced" rather than substituting something else.
        """
        if not legs:
            return {}
        provider = self.provider
        if self.provider_name == "hybrid":
            if self.db is None:
                return {}
            try:
                provider = build_live_provider(self.db)
            except (UnknownFlightProviderError, ProviderError):
                return {}

        lookup = getattr(provider, "one_way_legs", None)
        if not callable(lookup):
            return {}
        self.deals_provider_attempted = True
        # Later hops can fall outside the departure window, so the lookup covers
        # the window plus a full trip's length beyond it.
        window = DateRange(
            start=request.startDate,
            end=request.endDate + timedelta(days=request.maxTripLengthDays),
        )
        try:
            fares = lookup(legs, window)
        except ProviderError:
            return {}
        self.deals_provider_succeeded = any(fares.values())
        return fares

    def _targeted_round_trip_fares(self, provider, request: TripSearchRequest, scope: DestinationScope):
        """Ask the provider about exactly the places this search named."""
        routes = getattr(provider, "round_trips_for", None)
        if not callable(routes):
            return []
        self.deals_provider_attempted = True
        route_args = (
            request.originAirports,
            list(scope.query_targets),
            DateRange(start=request.startDate, end=request.endDate),
        )
        try:
            return routes(*route_args, direct_only=request.directOnly)
        except TypeError as exc:
            # Alternative provider adapters may not accept every keyword; degrade
            # rather than failing a search over a signature mismatch.
            if "direct_only" not in str(exc):
                raise
            return routes(*route_args)

    @staticmethod
    def _filter_round_trip_fares(fares, request: TripSearchRequest):
        countries = {code.strip().upper() for code in request.destinationCountries}
        regions = {value.strip().casefold() for value in request.destinationRegions}
        continents = {value.strip().casefold() for value in request.destinationContinents}
        origins = {code.strip().upper() for code in request.originAirports}
        destinations = (
            {canonical_code(code) for code in request.destinationAirports}
            if request.destinationAirports
            else None
        )
        filtered = []
        for fare in fares:
            destination = canonical_code(fare.destination)
            if destination in origins or not is_flightable_place(destination):
                continue
            if destinations is not None and not scope_matches(destination, destinations):
                continue
            if not place_matches_filters(
                destination,
                country_codes=countries or None,
                regions=regions or None,
                continents=continents or None,
                exclude_europe=request.excludeEurope,
            ):
                continue
            if request.directOnly and (fare.stops or 0) > 0:
                continue
            if fare_is_too_old(fare):
                continue
            filtered.append(fare.model_copy(update={"destination": destination}))
        return merge_duplicate_fares(filtered)

    def _cache_deals(self, deals_repo: CachedDealsRepository, fares) -> None:
        """Best-effort cache write: a cache problem must never fail the search."""
        try:
            deals_repo.upsert_deals(fares)
        except SQLAlchemyError:
            logger.warning("deals_cache_write_failed", exc_info=True)
            if self.db is not None:
                self.db.rollback()

    def apply_deal_metadata(self, metadata: ProviderMetadata) -> ProviderMetadata:
        metadata.cachedResultsUsed = metadata.cachedResultsUsed or self.deals_cache_used
        metadata.liveProviderAttempted = metadata.liveProviderAttempted or self.deals_provider_attempted
        metadata.liveProviderSucceeded = metadata.liveProviderSucceeded or self.deals_provider_succeeded
        if self.provider.name == "travelpayouts":
            metadata.providerWarnings = list(dict.fromkeys([*metadata.providerWarnings, *self.provider.warnings]))
            metadata.requestsAttempted = self.provider.requests_attempted or metadata.requestsAttempted
        return metadata

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
        # cache warm. Searches that named a destination always go live (rarer,
        # and the cache cannot be trusted to already cover that place).
        if self.resolve_scope(request).is_anywhere and CachedDealsRepository(self.db).has_fresh(
            request.originAirports
        ):
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
        if (
            provider.name == "travelpayouts"
            and not request.returnOriginAirports
            and self.resolve_scope(request).is_targeted
        ):
            # A simple return gets the provider's real round-trip bundle in
            # discover_round_trip_fares; avoid two redundant one-way route calls.
            return []
        if request.destinationAirports or request.returnOriginAirports:
            # Targeted search: origins → chosen destinations, returns back to the
            # origins from the fly-home airports (multi-city) or the destinations
            # themselves. Live providers spend their request budget on exactly
            # the routes the user asked for.
            outbound_scope = request.destinationAirports or request.returnOriginAirports or []
            return_scope = request.returnOriginAirports or request.destinationAirports or []
            outbound_flights = provider.search_flights(
                request.originAirports,
                request.startDate,
                request.endDate,
                destination_codes=outbound_scope,
                direct_only=request.directOnly,
            )
            return_flights = provider.search_flights(
                return_scope,
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


def fare_is_too_old(fare, today: date | None = None) -> bool:
    """Whether the provider last saw this price too long ago to quote it.

    A backstop, not the main control: the provider's data tops out around a week
    old anyway, and fare age is mostly handled by ranking so a thin route can
    still show the only fare that exists. A fare with no sighting date is kept —
    unknown age is not the same as known-stale, and the UI says which it is.
    """
    if fare.observedAt is None:
        return False
    age_days = ((today or date.today()) - fare.observedAt.date()).days
    return age_days > settings.max_fare_age_days


def merge_duplicate_fares(fares: list) -> list:
    """Collapse fares for the same route and dates, keeping the current price.

    The same trip arrives from more than one provider endpoint — the price
    calendar covers every departure date, prices_for_dates carries the exact-fare
    booking link — and the copies can disagree because they were seen days apart.
    The most recent sighting wins the price, because an older cheaper copy is a
    price that has since moved and is what makes our number disagree with the
    booking page. Links are carried across from whichever copy had one, so
    preferring the newer price never costs the traveller the exact-fare link.
    """
    best: dict[tuple, object] = {}
    order: list[tuple] = []
    for fare in fares:
        key = (fare.origin.upper(), fare.destination.upper(), fare.departureDate, fare.returnDate)
        existing = best.get(key)
        if existing is None:
            best[key] = fare
            order.append(key)
            continue
        winner, loser = (fare, existing) if _fare_is_newer(fare, existing) else (existing, fare)
        updates = {}
        for field in ("bookingUrl", "affiliateUrl", "expiresAt"):
            if getattr(winner, field) is None and getattr(loser, field) is not None:
                updates[field] = getattr(loser, field)
        best[key] = winner.model_copy(update=updates) if updates else winner
    return [best[key] for key in order]


def _fare_is_newer(candidate, current) -> bool:
    """Whether ``candidate`` is a more recent sighting of the same trip."""
    if candidate.observedAt and current.observedAt:
        if candidate.observedAt != current.observedAt:
            return candidate.observedAt > current.observedAt
        return candidate.price < current.price
    if candidate.observedAt:
        return True
    if current.observedAt:
        return False
    return candidate.price < current.price


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
