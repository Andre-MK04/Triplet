import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.data.search_destinations import SEARCH_DESTINATIONS
from app.db.repositories.flights_repository import FlightsRepository
from app.providers.caching import cache_flights
from app.models import Flight
from app.providers.errors import ProviderError
from app.providers.flight_provider import (
    DateRange,
    FlightProvider,
    ProviderCapabilities,
    ProviderStatus,
    SearchConstraints,
    SmokeTestResult,
    TripLengthRange,
    sample_search_dates,
    sanitize_flight_summary,
)
from app.providers.skyscanner.affiliate_links import SkyscannerAffiliateLinkBuilder
from app.providers.skyscanner.client import SkyscannerHttpClient, SkyscannerNoResultsError
from app.providers.skyscanner.mapper import map_live_response_to_flights

logger = logging.getLogger(__name__)


class SkyscannerFlightProvider(FlightProvider):
    """Skyscanner Travel API adapter. Dormant unless partner access is granted.

    Access requires an approved Skyscanner partner or commercial agreement, so this
    provider stays `requires_approval` until SKYSCANNER_API_KEY is configured.
    """

    name = "skyscanner"

    def __init__(
        self,
        db: Session | None = None,
        client: SkyscannerHttpClient | None = None,
        max_requests: int | None = None,
        cache_enabled: bool | None = None,
        affiliate_builder: SkyscannerAffiliateLinkBuilder | None = None,
    ):
        super().__init__()
        self.db = db
        self.client = client or SkyscannerHttpClient()
        self.max_requests = max_requests or settings.skyscanner_max_requests_per_search
        self.cache_enabled = settings.skyscanner_cache_enabled if cache_enabled is None else cache_enabled
        self.affiliate_builder = affiliate_builder or SkyscannerAffiliateLinkBuilder()

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
        search_dates = sample_search_dates(date_range.start, date_range.end, max_dates=14)
        flights: list[Flight] = []

        if not settings.skyscanner_api_enabled:
            self.warnings.append("Skyscanner API is disabled; no Skyscanner fares were fetched.")
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
                        payload = self.client.run_live_price_search(
                            build_one_way_live_search_payload(origin, destination, departure_date)
                        )
                    except SkyscannerNoResultsError:
                        continue
                    flights.extend(self.normalize_response_to_internal_flights(payload))

        return self._finalize(flights)

    def normalize_response_to_internal_flights(self, raw_response: dict) -> list[Flight]:
        mapping = map_live_response_to_flights(raw_response)
        self.raw_offers_count += mapping.raw_offers_count
        self.mapped_flights_count += mapping.mapped_flights_count
        self.skipped_offers_count += mapping.skipped_offers_count
        self.deep_links_returned += mapping.deep_links_returned
        self.warnings.extend(mapping.warnings)
        return mapping.flights

    def get_provider_status(self) -> ProviderStatus:
        configured = bool(settings.skyscanner_api_key)
        enabled = settings.skyscanner_api_enabled
        if not configured:
            access = "requires_approval"
        elif not enabled:
            access = "disabled"
        else:
            access = "available"
        warnings = []
        if not configured:
            warnings.append("Skyscanner Travel API access requires partner approval; no API key configured.")
        if settings.skyscanner_affiliate_enabled and not settings.skyscanner_media_partner_id:
            warnings.append("Skyscanner affiliate links enabled but no media partner ID configured.")
        return ProviderStatus(
            name=self.name,
            accessStatus=access,
            enabled=enabled,
            configured=configured,
            implementationStatus="adapter_only",
            capabilities=ProviderCapabilities(
                oneWaySearch=True,
                returnSearch=True,
                multiCityOrOpenJaw=False,
                flexibleDateSearch=True,
                priceHistory=False,
                deepLinks=True,
                affiliateLinks=True,
                baggageInfo=False,
                liveAvailability=True,
            ),
            requiredEnvVars=[
                "SKYSCANNER_API_ENABLED",
                "SKYSCANNER_API_KEY",
                "SKYSCANNER_MEDIA_PARTNER_ID",
            ],
            rateLimitNotes=(
                f"Live search create+poll per route/date; capped at "
                f"{settings.skyscanner_max_requests_per_search} requests per search."
            ),
            warnings=warnings,
        )

    def smoke_test(
        self,
        origin: str = "VIE",
        destination: str = "ALC",
        departure_date: date | None = None,
        max_results: int = 3,
    ) -> SmokeTestResult:
        status = self.get_provider_status()
        departure_date = departure_date or (date.today() + timedelta(days=45))
        result = SmokeTestResult(
            provider=self.name,
            enabled=status.enabled,
            configured=status.configured,
            origin=origin.upper(),
            destination=destination.upper(),
            departureDate=departure_date.isoformat(),
            warnings=list(status.warnings),
        )
        affiliate_link = self.affiliate_builder.build_day_view_link(
            origin, destination, departure_date, utm_term=f"{origin}-{destination}"
        )
        result.affiliateLinkGenerated = bool(affiliate_link)

        if not status.enabled:
            result.warnings.append("Skyscanner API is disabled.")
            return result
        if not status.configured:
            result.warnings.append("Skyscanner API key is missing.")
            return result

        try:
            payload = self.client.run_live_price_search(
                build_one_way_live_search_payload(origin, destination, departure_date)
            )
        except SkyscannerNoResultsError:
            result.apiOk = True
            result.ok = True
            result.warnings.append("Skyscanner returned no flight offers for the smoke-test route.")
            return result
        except ProviderError as exc:
            result.warnings.append(str(exc))
            return result

        result.apiOk = True
        result.ok = True
        flights = self.normalize_response_to_internal_flights(payload)
        result.rawOffersCount = self.raw_offers_count
        result.mappedFlightsCount = self.mapped_flights_count
        result.skippedOffersCount = self.skipped_offers_count
        result.deepLinksReturned = self.deep_links_returned
        result.warnings.extend(self.warnings)
        if flights:
            result.sampleFlight = sanitize_flight_summary(flights[0])
        return result

    def _finalize(self, flights: list[Flight]) -> list[Flight]:
        deduped = deduplicate_flights(flights)
        if self.cache_enabled and self.db and deduped:
            self.cached_flights_count += cache_flights(self.db, deduped)
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
    return sample_search_dates(start_date, end_date, max_dates)


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
        elif flight.confidenceLevel == "live" and existing.confidenceLevel != "live":
            best[key] = flight
        elif flight.price < existing.price:
            best[key] = flight
    return list(best.values())
