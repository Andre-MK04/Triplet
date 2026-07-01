import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.data.search_destinations import SEARCH_DESTINATIONS
from app.db.repositories.flights_repository import FlightsRepository
from app.models import Flight
from app.providers.amadeus.client import AmadeusHttpClient, AmadeusNoResultsError
from app.providers.amadeus.mapper import map_amadeus_offers
from app.providers.flight_provider import FlightProvider


logger = logging.getLogger(__name__)


class AmadeusFlightProvider(FlightProvider):
    def __init__(
        self,
        db: Session | None = None,
        client: AmadeusHttpClient | None = None,
        max_requests: int | None = None,
        cache_enabled: bool | None = None,
    ):
        self.db = db
        self.client = client or AmadeusHttpClient()
        self.max_requests = max_requests or settings.amadeus_max_requests_per_search
        self.cache_enabled = settings.amadeus_cache_enabled if cache_enabled is None else cache_enabled
        self.requests_attempted = 0
        self.raw_offers_count = 0
        self.mapped_flights_count = 0
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

        for origin in origin_codes:
            for destination in destinations:
                if origin == destination:
                    continue
                for departure_date in search_dates:
                    if self.requests_attempted >= self.max_requests:
                        return self._finalize(flights)
                    self.requests_attempted += 1
                    try:
                        payload = self.client.get(
                            "/v2/shopping/flight-offers",
                            {
                                "originLocationCode": origin,
                                "destinationLocationCode": destination,
                                "departureDate": departure_date.isoformat(),
                                "adults": 1,
                                "currencyCode": "EUR",
                                "max": 10,
                                "nonStop": str(direct_only).lower(),
                            },
                        )
                    except AmadeusNoResultsError:
                        continue
                    mapping = map_amadeus_offers(payload)
                    self.raw_offers_count += mapping.raw_offers_count
                    self.mapped_flights_count += mapping.mapped_flights_count
                    self.warnings.extend(mapping.warnings)
                    flights.extend(mapping.flights)

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
            self.warnings.append("Live provider returned no supported direct flight offers for this search.")
        self.warnings.append("Connecting or complex itineraries may be skipped in this MVP.")
        logger.info(
            "amadeus_search requests=%s/%s raw_offers=%s mapped=%s cached=%s warnings=%s",
            self.requests_attempted,
            self.max_requests,
            self.raw_offers_count,
            self.mapped_flights_count,
            self.cached_flights_count,
            len(self.warnings),
        )
        return sorted(deduped, key=lambda flight: flight.price)


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


def deduplicate_flights(flights: list[Flight]) -> list[Flight]:
    best: dict[tuple, Flight] = {}
    for flight in flights:
        key = (
            flight.origin,
            flight.destination,
            flight.departureDateTime,
            flight.arrivalDateTime,
            flight.airline,
            round(flight.price, 2),
        )
        existing = best.get(key)
        if not existing:
            best[key] = flight
        elif existing.provider != "amadeus" and flight.provider == "amadeus":
            best[key] = flight
        elif flight.price < existing.price:
            best[key] = flight
    return list(best.values())
