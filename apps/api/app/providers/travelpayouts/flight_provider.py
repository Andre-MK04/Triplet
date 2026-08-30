import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.db.repositories.flights_repository import FlightsRepository
from app.providers.caching import cache_flights
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
from app.providers.errors import ProviderError
from app.providers.travelpayouts.client import TravelpayoutsHttpClient
from app.providers.travelpayouts.mapper import (
    RoundTripFare,
    map_city_directions_response,
    map_prices_for_dates_response_to_flights,
    map_round_trip_rows,
)

logger = logging.getLogger(__name__)

# A targeted query asks for a country as often as a single city, so ask for a
# generous page: one country query can legitimately return dozens of cities.
TARGETED_ROUTE_LIMIT = 100


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
        origins = origin_airports or []
        destinations = destination_scope or []
        months = months_in_range(date_range)
        flights: list[Flight] = []

        if not settings.travelpayouts_api_enabled:
            self.warnings.append("Travelpayouts API is disabled; no indicative fares were fetched.")
            return self._finalize(flights)

        if not destinations:
            # Open searches are answered by the round-trip primitives
            # (round_trips_in_window / discover_round_trips), not by expanding
            # one-way routes into a matrix. Nothing to warn a traveller about.
            logger.info("travelpayouts_search skipped one-way matrix for an open destination scope")
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
                        payload = self.client.prices_for_dates(
                            origin,
                            destination,
                            month,
                            direct_only=bool(constraints and constraints.directOnly),
                        )
                    except ProviderNoResultsError:
                        continue
                    flights.extend(self.normalize_response_to_internal_flights(payload))

        return self._finalize(flights, date_range)

    def discover_round_trips(self, origins: list[str]) -> list[RoundTripFare]:
        """Cheapest round trips from each origin to every popular destination.

        Uses /v1/city-directions — the provider discovers destinations, so results
        are not limited to a hardcoded list. Returns [] (never raises) so discovery
        can augment a search without being able to break it.
        """
        if not settings.travelpayouts_api_enabled:
            return []
        fares: list[RoundTripFare] = []
        for origin in origins:
            self.requests_attempted += 1
            try:
                payload = self.client.city_directions(origin)
            except ProviderError as exc:
                self.warnings.append(f"city-directions failed for {origin}: {exc}")
                continue
            mapped = map_city_directions_response(payload, origin, settings.travelpayouts_marker)
            fares.extend(
                sorted(mapped, key=lambda fare: fare.price)[
                    : settings.travelpayouts_discovery_limit_per_origin
                ]
            )
        return fares

    def round_trips_in_window(self, origins: list[str], date_range: DateRange) -> list[RoundTripFare]:
        """Cheapest round trips from each origin *within the requested months*.

        city-directions answers "cheapest from here, ever", so its fares usually
        sit outside the dates someone actually asked about — an open search for
        October would otherwise be answered mostly with fares for other months.
        This asks the per-route price API with no destination, which returns real
        in-window round trips across whatever cities have them. One request per
        origin per month. Returns [] (never raises).
        """
        if not settings.travelpayouts_api_enabled:
            return []
        fares: list[RoundTripFare] = []
        for month in months_in_range(date_range):
            for origin in origins:
                if self.requests_attempted >= self.max_requests:
                    return fares
                self.requests_attempted += 1
                try:
                    payload = self.client.prices_for_dates(
                        origin,
                        None,
                        month,
                        one_way=False,
                        limit=TARGETED_ROUTE_LIMIT,
                    )
                except ProviderNoResultsError:
                    continue
                except ProviderError as exc:
                    self.warnings.append(f"open search failed for {origin} in {month}: {exc}")
                    continue
                fares.extend(map_round_trip_rows(payload, settings.travelpayouts_marker))
        return fares

    def round_trips_for(
        self,
        origins: list[str],
        destinations: list[str],
        date_range: DateRange,
        direct_only: bool = False,
    ) -> list[RoundTripFare]:
        """Round-trip fares for requested destinations (prices_for_dates one_way=false).

        ``destinations`` may hold city/airport codes or ISO country codes, so a
        request for a whole country is one query rather than a guess at its
        cities. Used whenever the traveller named a destination, so that place
        always yields something — even a pricey one — instead of depending on
        whichever routes the shared discovery cache happens to hold.

        Queries are planned month by month and destination before origin, so a
        request budget that runs out costs extra origins rather than dropping
        destinations the traveller explicitly asked about. Returns [] (never
        raises); respects the per-search request cap.
        """
        if not settings.travelpayouts_api_enabled:
            return []
        fares: list[RoundTripFare] = []
        skipped_origins: set[str] = set()
        for origin, destination, month in plan_route_queries(origins, destinations, date_range):
            if self.requests_attempted >= self.max_requests:
                skipped_origins.add(origin.upper())
                continue
            self.requests_attempted += 1
            try:
                payload = self.client.prices_for_dates(
                    origin,
                    destination,
                    month,
                    one_way=False,
                    direct_only=direct_only,
                    limit=TARGETED_ROUTE_LIMIT,
                )
            except ProviderNoResultsError:
                continue
            except ProviderError as exc:
                self.warnings.append(f"round-trip query failed for {origin}-{destination}: {exc}")
                continue
            fares.extend(map_round_trip_rows(payload, settings.travelpayouts_marker))
        if skipped_origins:
            self.warnings.append(
                "Checked as many routes as this search allows; "
                f"{', '.join(sorted(skipped_origins))} was not covered for every date range."
            )
        return fares

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
                "Cached data API: broad discovery is one request per origin and targeted searches are one "
                f"request per route/month. Targeted searches are capped at {settings.travelpayouts_max_requests_per_search} "
                f"requests; discovery retains up to {settings.travelpayouts_discovery_limit_per_origin} destinations per origin."
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
            self.cached_flights_count += cache_flights(self.db, deduped)
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


def plan_route_queries(
    origins: list[str],
    destinations: list[str],
    date_range: DateRange,
) -> list[tuple[str, str, str]]:
    """Order (origin, destination, month) queries so a truncated plan still covers
    every requested destination.

    Month is the outermost loop and destination sits inside origin, so the first
    origin covers all destinations for the first month before anything goes
    deeper. Truncation then costs extra origins and later months, never a
    destination the traveller named.
    """
    plan: list[tuple[str, str, str]] = []
    for month in months_in_range(date_range):
        for origin in origins:
            for destination in destinations:
                if origin.strip().upper() == destination.strip().upper():
                    continue
                plan.append((origin, destination, month))
    return plan


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
