import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Flight, ProviderMetadata, TripSearchRequest
from app.providers.amadeus import AmadeusApiError, AmadeusAuthError, AmadeusConfigError
from app.providers import AmadeusFlightProvider, DatabaseFlightProvider, FlightProvider, MockFlightProvider


class UnknownFlightProviderError(ValueError):
    pass


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
            return self._search_hybrid(request)

        outbound_flights = self.provider.search_outbound_flights(
            origin_codes=request.originAirports,
            start_date=request.startDate,
            end_date=request.endDate,
            direct_only=request.directOnly,
        )
        return_flights = self.provider.search_return_flights(
            return_destination_codes=request.originAirports,
            start_date=request.startDate,
            end_date=request.endDate + timedelta(days=request.maxTripLengthDays),
            direct_only=request.directOnly,
        )
        flights_by_id = {flight.id: flight for flight in outbound_flights + return_flights}
        flights = list(flights_by_id.values())
        metadata = ProviderMetadata(providerUsed=self.provider_name)
        if self.provider_name == "amadeus":
            metadata.liveProviderAttempted = True
            metadata.liveProviderSucceeded = bool(flights)
            metadata.amadeusRequestsAttempted = getattr(self.provider, "requests_attempted", None)
            metadata.amadeusRequestsLimit = getattr(self.provider, "max_requests", None)
            metadata.rawOffersCount = getattr(self.provider, "raw_offers_count", None)
            metadata.mappedFlightsCount = getattr(self.provider, "mapped_flights_count", None)
            metadata.providerWarnings = list(dict.fromkeys(getattr(self.provider, "warnings", [])))
        else:
            metadata.cachedResultsUsed = self.provider_name == "database"

        logging.getLogger(__name__).info(
            "flight_search provider=%s flights=%s live_attempted=%s cached=%s",
            metadata.providerUsed,
            len(flights),
            metadata.liveProviderAttempted,
            metadata.cachedResultsUsed,
        )
        return FlightSearchResult(
            flights=flights,
            metadata=metadata,
        )

    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
    ) -> list[Flight]:
        return self.provider.search_flights(origin_codes, start_date, end_date, destination_codes)

    def _build_provider(self, db: Session | None) -> FlightProvider:
        if self.provider_name == "database":
            if db is None:
                raise UnknownFlightProviderError("Database flight provider requires a database session.")
            return DatabaseFlightProvider(db)
        if self.provider_name == "mock":
            return MockFlightProvider([])
        if self.provider_name == "amadeus":
            return AmadeusFlightProvider(db=db)
        if self.provider_name == "hybrid":
            if db is None:
                raise UnknownFlightProviderError("Hybrid flight provider requires a database session.")
            return DatabaseFlightProvider(db)
        raise UnknownFlightProviderError(
            f"Unknown flight provider '{self.provider_name}'. Use FLIGHT_PROVIDER=database."
        )

    def _search_hybrid(self, request: TripSearchRequest) -> FlightSearchResult:
        if self.db is None:
            raise UnknownFlightProviderError("Hybrid flight provider requires a database session.")

        database_provider = DatabaseFlightProvider(self.db)
        cached_flights = self._search_with_provider(database_provider, request)
        try:
            amadeus_provider = AmadeusFlightProvider(db=self.db)
            amadeus_flights = self._search_with_provider(amadeus_provider, request)
            merged = deduplicate_flights(cached_flights + amadeus_flights)
            metadata = ProviderMetadata(
                providerUsed="hybrid",
                liveProviderAttempted=True,
                liveProviderSucceeded=bool(amadeus_flights),
                cachedResultsUsed=bool(cached_flights),
                amadeusRequestsAttempted=getattr(amadeus_provider, "requests_attempted", None)
                if "amadeus_provider" in locals()
                else None,
                amadeusRequestsLimit=getattr(amadeus_provider, "max_requests", None)
                if "amadeus_provider" in locals()
                else None,
                rawOffersCount=getattr(amadeus_provider, "raw_offers_count", None)
                if "amadeus_provider" in locals()
                else None,
                mappedFlightsCount=getattr(amadeus_provider, "mapped_flights_count", None)
                if "amadeus_provider" in locals()
                else None,
                providerWarnings=list(dict.fromkeys(getattr(amadeus_provider, "warnings", [])))
                if "amadeus_provider" in locals()
                else [],
            )
            return FlightSearchResult(
                flights=merged,
                metadata=metadata,
            )
        except (AmadeusConfigError, AmadeusAuthError, AmadeusApiError) as exc:
            logging.getLogger(__name__).warning("hybrid_fallback reason=%s cached_flights=%s", type(exc).__name__, len(cached_flights))
            return FlightSearchResult(
                flights=cached_flights,
                metadata=ProviderMetadata(
                    providerUsed="database",
                    liveProviderAttempted=True,
                    liveProviderSucceeded=False,
                    cachedResultsUsed=True,
                    amadeusRequestsLimit=settings.amadeus_max_requests_per_search,
                    providerWarnings=[f"Using cached/database fares because Amadeus failed: {exc}"],
                ),
            )

    def _search_with_provider(self, provider: FlightProvider, request: TripSearchRequest) -> list[Flight]:
        outbound_flights = provider.search_outbound_flights(
            request.originAirports,
            request.startDate,
            request.endDate,
            request.directOnly,
        )
        return_flights = provider.search_return_flights(
            request.originAirports,
            request.startDate,
            request.endDate + timedelta(days=request.maxTripLengthDays),
            request.directOnly,
        )
        return deduplicate_flights(outbound_flights + return_flights)


def deduplicate_flights(flights: list[Flight]) -> list[Flight]:
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
        elif flight.provider == "amadeus" and existing.provider != "amadeus":
            by_key[key] = flight
        elif flight.price < existing.price:
            by_key[key] = flight
    return list(by_key.values())
