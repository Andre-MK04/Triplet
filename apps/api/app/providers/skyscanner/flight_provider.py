import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.data.search_destinations import SEARCH_DESTINATIONS
from app.db.repositories.flights_repository import FlightsRepository
from app.models import Flight
from app.providers.flight_provider import FlightProvider
from app.providers.skyscanner.affiliate_links import SkyscannerAffiliateLinkBuilder
from app.providers.skyscanner.client import SkyscannerHttpClient, SkyscannerNoResultsError
from app.providers.skyscanner.mapper import map_live_response_to_flights

logger = logging.getLogger(__name__)


class SkyscannerFlightProvider(FlightProvider):
    def __init__(
        self,
        db: Session | None = None,
        client: SkyscannerHttpClient | None = None,
        max_requests: int | None = None,
        cache_enabled: bool | None = None,
        affiliate_builder: SkyscannerAffiliateLinkBuilder | None = None,
    ):
        self.db = db
        self.client = client or SkyscannerHttpClient()
        self.max_requests = max_requests or settings.skyscanner_max_requests_per_search
        self.cache_enabled = settings.skyscanner_cache_enabled if cache_enabled is None else cache_enabled
        self.affiliate_builder = affiliate_builder or SkyscannerAffiliateLinkBuilder()
        self.requests_attempted = 0
        self.raw_offers_count = 0
        self.mapped_flights_count = 0
        self.skipped_offers_count = 0
        self.deep_links_returned = 0
        self.affiliate_links_generated = 0
        self.cached_flights_count = 0
        self.warnings: list[str] = []

    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
        direct_only: bool = True,
    ) -> list[Flight]:
        destinations = destination_codes or SEARCH_DESTINATIONS
        search_dates = generate_search_dates(start_date, end_date, max_dates=14)
        flights: list[Flight] = []

        if not settings.skyscanner_api_enabled:
            self.warnings.append("Skyscanner API is disabled; using affiliate fallback links only when possible.")
            return self._finalize(add_affiliate_links([], origin_codes, destinations, search_dates, self.affiliate_builder, self))

        for origin in origin_codes:
            for destination in destinations:
                if origin == destination:
                    continue
                for departure_date in search_dates:
                    if self.requests_attempted >= self.max_requests:
                        return self._finalize(flights)
                    self.requests_attempted += 1
                    try:
                        payload = self.client.run_live_price_search(
                            build_one_way_live_search_payload(origin, destination, departure_date)
                        )
                    except SkyscannerNoResultsError:
                        continue
                    mapping = map_live_response_to_flights(payload)
                    self.raw_offers_count += mapping.raw_offers_count
                    self.mapped_flights_count += mapping.mapped_flights_count
                    self.skipped_offers_count += mapping.skipped_offers_count
                    self.deep_links_returned += mapping.deep_links_returned
                    self.warnings.extend(mapping.warnings)
                    flights.extend(mapping.flights)

        if not flights:
            flights = add_affiliate_links([], origin_codes, destinations, search_dates, self.affiliate_builder, self)
        return self._finalize(flights)

    def search_outbound_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.search_flights(origin_codes, start_date, end_date, SEARCH_DESTINATIONS, direct_only)

    def search_return_flights(
        self,
        return_destination_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.search_flights(SEARCH_DESTINATIONS, start_date, end_date, return_destination_codes, direct_only)

    def _finalize(self, flights: list[Flight]) -> list[Flight]:
        deduped = deduplicate_flights(flights)
        if self.cache_enabled and self.db and deduped:
            FlightsRepository(self.db).upsert_flights(deduped)
            self.cached_flights_count += len(deduped)
        if self.requests_attempted and self.mapped_flights_count == 0:
            self.warnings.append("Skyscanner returned no supported live flight offers for this search.")
        logger.info(
            "skyscanner_search requests=%s/%s raw_offers=%s mapped=%s skipped=%s deep_links=%s cached=%s",
            self.requests_attempted,
            self.max_requests,
            self.raw_offers_count,
            self.mapped_flights_count,
            self.skipped_offers_count,
            self.deep_links_returned,
            self.cached_flights_count,
        )
        return sorted(deduped, key=lambda flight: flight.price)


def build_one_way_live_search_payload(origin: str, destination: str, departure_date: date) -> dict:
    return {
        "query": {
            "market": settings.skyscanner_market,
            "locale": settings.skyscanner_locale,
            "currency": settings.skyscanner_currency,
            "queryLegs": [
                {
                    "originPlaceId": {"iata": origin.upper()},
                    "destinationPlaceId": {"iata": destination.upper()},
                    "date": {
                        "year": departure_date.year,
                        "month": departure_date.month,
                        "day": departure_date.day,
                    },
                }
            ],
            "adults": 1,
            "cabinClass": "CABIN_CLASS_ECONOMY",
        }
    }


def generate_search_dates(start_date: date, end_date: date, max_dates: int) -> list[date]:
    if end_date < start_date:
        return []
    total_days = (end_date - start_date).days
    step = 1 if total_days <= 14 else 3
    dates = []
    current = start_date
    while current <= end_date and len(dates) < max_dates:
        dates.append(current)
        current += timedelta(days=step)
    if end_date not in dates and len(dates) < max_dates:
        dates.append(end_date)
    return dates[:max_dates]


def add_affiliate_links(
    flights: list[Flight],
    origin_codes: list[str],
    destination_codes: list[str],
    search_dates: list[date],
    builder: SkyscannerAffiliateLinkBuilder,
    provider: SkyscannerFlightProvider,
) -> list[Flight]:
    if flights or not builder.can_generate() or not search_dates:
        return flights
    origin = origin_codes[0]
    destination = next((code for code in destination_codes if code != origin), destination_codes[0])
    link = builder.build_day_view_link(origin, destination, search_dates[0], utm_term=f"{origin}-{destination}")
    if not link:
        return flights
    provider.affiliate_links_generated += 1
    provider.warnings.append("Skyscanner live fares were unavailable; generated an affiliate search link fallback.")
    return [
        Flight(
            id=f"skyscanner-affiliate-{origin}-{destination}-{search_dates[0].isoformat()}",
            origin=origin,
            destination=destination,
            departureDateTime=datetime.combine(search_dates[0], time(hour=9)),
            arrivalDateTime=datetime.combine(search_dates[0], time(hour=11)),
            airline="Skyscanner search",
            price=0,
            currency=settings.skyscanner_currency,
            bookingUrl=link,
            provider="skyscanner",
            isLive=False,
        )
    ]


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
        if not existing:
            best[key] = flight
        elif flight.provider == "skyscanner" and existing.provider != "skyscanner":
            best[key] = flight
        elif flight.price < existing.price:
            best[key] = flight
    return list(best.values())
