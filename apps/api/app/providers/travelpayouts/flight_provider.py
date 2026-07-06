import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.data.search_destinations import SEARCH_DESTINATIONS
from app.db.repositories.flights_repository import FlightsRepository
from app.models import Flight
from app.providers.errors import ProviderNoResultsError
from app.providers.flight_provider import (
    DateRange,
    FlightProvider,
    ProviderCapabilities,
    ProviderStatus,
    SearchConstraints,
    TripLengthRange,
)
from app.providers.travelpayouts.client import TravelpayoutsHttpClient
from app.providers.travelpayouts.mapper import map_prices_for_dates_response_to_flights

logger = logging.getLogger(__name__)


class TravelpayoutsAviasalesProvider(FlightProvider):
    """Travelpayouts/Aviasales Data API adapter.

    Returns cached market prices (confidence: indicative), never live availability.
    Every mapped fare links to the Aviasales search page, with the affiliate marker
    appended when TRAVELPAYOUTS_MARKER is configured.
    """

    name = "travelpayouts"
    # Cached data is month-granular; smoke-test a ~4-week window, not a single day.
    smoke_test_window_days = 27

    def __init__(
        self,
        db: Session | None = None,
        client: TravelpayoutsHttpClient | None = None,
        max_requests: int | None = None,
        cache_enabled: bool | None = None,
    ):
        super().__init__()
        self.db = db
        self.client = client or TravelpayoutsHttpClient()
        self.max_requests = max_requests or settings.travelpayouts_max_requests_per_search
        self.cache_enabled = settings.travelpayouts_cache_enabled if cache_enabled is None else cache_enabled

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
        months = months_in_range(date_range)
        flights: list[Flight] = []

        if not settings.travelpayouts_api_enabled:
            self.warnings.append("Travelpayouts API is disabled; no indicative fares were fetched.")
            return self._finalize(flights)

        for origin in origins:
            for destination in destinations:
                if origin == destination:
                    continue
                for month in months:
                    if self.requests_attempted >= self.max_requests:
                        return self._finalize(flights, date_range)
                    self.requests_attempted += 1
                    try:
                        payload = self.client.prices_for_dates(origin, destination, month)
                    except ProviderNoResultsError:
                        continue
                    flights.extend(self.normalize_response_to_internal_flights(payload))

        return self._finalize(flights, date_range)

    def normalize_response_to_internal_flights(self, raw_response: dict) -> list[Flight]:
        mapping = map_prices_for_dates_response_to_flights(raw_response, marker=settings.travelpayouts_marker)
        self.raw_offers_count += mapping.raw_offers_count
        self.mapped_flights_count += mapping.mapped_flights_count
        self.skipped_offers_count += mapping.skipped_offers_count
        self.deep_links_returned += mapping.deep_links_returned
        self.affiliate_links_generated += mapping.affiliate_links_generated
        self.warnings.extend(mapping.warnings)
        return mapping.flights

    def get_provider_status(self) -> ProviderStatus:
        configured = bool(settings.travelpayouts_api_token)
        enabled = settings.travelpayouts_api_enabled
        if not configured:
            access = "not_configured"
        elif not enabled:
            access = "disabled"
        else:
            access = "available"
        warnings = []
        if not configured:
            warnings.append(
                "Travelpayouts API token is not configured; register at travelpayouts.com and set TRAVELPAYOUTS_API_TOKEN."
            )
        if configured and not settings.travelpayouts_marker:
            warnings.append("Travelpayouts affiliate marker is missing; links will not be attributed.")
        return ProviderStatus(
            name=self.name,
            accessStatus=access,
            enabled=enabled,
            configured=configured,
            implementationStatus="implemented",
            capabilities=ProviderCapabilities(
                oneWaySearch=True,
                returnSearch=True,
                multiCityOrOpenJaw=False,
                flexibleDateSearch=True,
                priceHistory=True,
                deepLinks=True,
                affiliateLinks=True,
                baggageInfo=False,
                liveAvailability=False,
            ),
            requiredEnvVars=[
                "TRAVELPAYOUTS_API_ENABLED",
                "TRAVELPAYOUTS_API_TOKEN",
                "TRAVELPAYOUTS_MARKER",
            ],
            rateLimitNotes=(
                "Cached data API, one request per route/month; prices are indicative, not live. "
                f"Capped at {settings.travelpayouts_max_requests_per_search} requests per search."
            ),
            warnings=warnings,
        )

    def _finalize(self, flights: list[Flight], date_range: DateRange | None = None) -> list[Flight]:
        if date_range:
            flights = [
                flight
                for flight in flights
                if date_range.start <= flight.departureDateTime.date() <= date_range.end
            ]
        deduped = deduplicate_flights(flights)
        if self.cache_enabled and self.db and deduped:
            FlightsRepository(self.db).upsert_flights(deduped)
            self.cached_flights_count += len(deduped)
        if self.requests_attempted and self.mapped_flights_count == 0:
            self.warnings.append("Travelpayouts returned no usable indicative fares for this search.")
        logger.info(
            "travelpayouts_search requests=%s/%s raw_offers=%s mapped=%s skipped=%s links=%s cached=%s",
            self.requests_attempted,
            self.max_requests,
            self.raw_offers_count,
            self.mapped_flights_count,
            self.skipped_offers_count,
            self.deep_links_returned,
            self.cached_flights_count,
        )
        return sorted(deduped, key=lambda flight: flight.price)


def months_in_range(date_range: DateRange) -> list[str]:
    """Unique YYYY-MM strings covering the range; the data API works per month."""
    months: list[str] = []
    year, month = date_range.start.year, date_range.start.month
    while (year, month) <= (date_range.end.year, date_range.end.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def deduplicate_flights(flights: list[Flight]) -> list[Flight]:
    best: dict[tuple, Flight] = {}
    for flight in flights:
        key = (
            flight.origin,
            flight.destination,
            flight.departureDateTime,
            flight.airline,
        )
        existing = best.get(key)
        if not existing or flight.price < existing.price:
            best[key] = flight
    return list(best.values())
