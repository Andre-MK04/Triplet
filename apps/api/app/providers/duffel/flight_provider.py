import logging
from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.data.search_destinations import SEARCH_DESTINATIONS
from app.db.repositories.flights_repository import FlightsRepository
from app.models import Flight
from app.providers.duffel.client import DuffelHttpClient
from app.providers.duffel.mapper import map_offer_request_response_to_flights
from app.providers.errors import ProviderNoResultsError
from app.providers.flight_provider import (
    DateRange,
    FlightProvider,
    ProviderCapabilities,
    ProviderStatus,
    SearchConstraints,
    TripLengthRange,
    sample_search_dates,
)

logger = logging.getLogger(__name__)

CABIN_CLASS_MAP = {
    "economy": "economy",
    "premium_economy": "premium_economy",
    "business": "business",
    "first": "first",
}


class DuffelFlightProvider(FlightProvider):
    """Duffel Flights API adapter. Search and offers only; Triplet never books.

    Duffel is a booking API, so offers have no public deep link. Fares are live
    at observation time and expire quickly; they are cached with expiry.
    """

    name = "duffel"

    def __init__(
        self,
        db: Session | None = None,
        client: DuffelHttpClient | None = None,
        max_requests: int | None = None,
        cache_enabled: bool | None = None,
    ):
        super().__init__()
        self.db = db
        self.client = client or DuffelHttpClient()
        self.max_requests = max_requests or settings.duffel_max_requests_per_search
        self.cache_enabled = settings.duffel_cache_enabled if cache_enabled is None else cache_enabled

    def search_flexible(
        self,
        origin_airports: list[str] | None,
        destination_scope: list[str] | None,
        date_range: DateRange,
        trip_length_range: TripLengthRange | None = None,
        constraints: SearchConstraints | None = None,
    ) -> list[Flight]:
        origins = origin_airports or SEARCH_DESTINATIONS
        destinations = destination_scope or SEARCH_DESTINATIONS
        constraints = constraints or SearchConstraints()
        # Duffel live searches are expensive; sample fewer dates than cheaper APIs.
        search_dates = sample_search_dates(date_range.start, date_range.end, max_dates=5)
        flights: list[Flight] = []

        if not settings.duffel_api_enabled:
            self.warnings.append("Duffel API is disabled; no Duffel fares were fetched.")
            return self._finalize(flights)

        for origin in origins:
            for destination in destinations:
                if origin == destination:
                    continue
                for departure_date in search_dates:
                    if self.requests_attempted >= self.max_requests:
                        return self._finalize(flights)
                    self.requests_attempted += 1
                    try:
                        payload = self.client.create_offer_request(
                            build_one_way_offer_request_payload(
                                origin,
                                destination,
                                departure_date,
                                passengers=constraints.passengers,
                                cabin=constraints.cabin,
                            )
                        )
                    except ProviderNoResultsError:
                        continue
                    flights.extend(self.normalize_response_to_internal_flights(payload))

        return self._finalize(flights)

    def normalize_response_to_internal_flights(self, raw_response: dict) -> list[Flight]:
        mapping = map_offer_request_response_to_flights(raw_response)
        self.raw_offers_count += mapping.raw_offers_count
        self.mapped_flights_count += mapping.mapped_flights_count
        self.skipped_offers_count += mapping.skipped_offers_count
        self.warnings.extend(mapping.warnings)
        return mapping.flights

    def get_provider_status(self) -> ProviderStatus:
        configured = bool(settings.duffel_api_key)
        enabled = settings.duffel_api_enabled
        if not configured:
            access = "not_configured"
        elif not enabled:
            access = "disabled"
        else:
            access = "available"
        warnings = []
        if not configured:
            warnings.append("Duffel API key is not configured; sign up at duffel.com and set DUFFEL_API_KEY.")
        return ProviderStatus(
            name=self.name,
            accessStatus=access,
            enabled=enabled,
            configured=configured,
            implementationStatus="implemented",
            capabilities=ProviderCapabilities(
                oneWaySearch=True,
                returnSearch=True,
                multiCityOrOpenJaw=True,
                flexibleDateSearch=False,
                priceHistory=False,
                deepLinks=False,
                affiliateLinks=False,
                baggageInfo=True,
                liveAvailability=True,
            ),
            requiredEnvVars=["DUFFEL_API_ENABLED", "DUFFEL_API_KEY"],
            rateLimitNotes=(
                "One offer request per route/date; live searches are metered per request. "
                f"Capped at {settings.duffel_max_requests_per_search} requests per search."
            ),
            warnings=warnings,
        )

    def _finalize(self, flights: list[Flight]) -> list[Flight]:
        deduped = deduplicate_flights(flights)
        if self.cache_enabled and self.db and deduped:
            FlightsRepository(self.db).upsert_flights(deduped)
            self.cached_flights_count += len(deduped)
        if self.requests_attempted and self.mapped_flights_count == 0:
            self.warnings.append("Duffel returned no supported flight offers for this search.")
        logger.info(
            "duffel_search requests=%s/%s raw_offers=%s mapped=%s skipped=%s cached=%s",
            self.requests_attempted,
            self.max_requests,
            self.raw_offers_count,
            self.mapped_flights_count,
            self.skipped_offers_count,
            self.cached_flights_count,
        )
        return sorted(deduped, key=lambda flight: flight.price)


def build_one_way_offer_request_payload(
    origin: str,
    destination: str,
    departure_date: date,
    passengers: int = 1,
    cabin: str = "economy",
) -> dict:
    return {
        "data": {
            "slices": [
                {
                    "origin": origin.upper(),
                    "destination": destination.upper(),
                    "departure_date": departure_date.isoformat(),
                }
            ],
            "passengers": [{"type": "adult"} for _ in range(max(passengers, 1))],
            "cabin_class": CABIN_CLASS_MAP.get(cabin, "economy"),
        }
    }


def deduplicate_flights(flights: list[Flight]) -> list[Flight]:
    best: dict[tuple, Flight] = {}
    for flight in flights:
        key = (
            flight.origin,
            flight.destination,
            flight.departureDateTime,
            flight.arrivalDateTime,
            flight.airline,
        )
        existing = best.get(key)
        if not existing or flight.price < existing.price:
            best[key] = flight
    return list(best.values())
