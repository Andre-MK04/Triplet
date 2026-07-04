from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel

from app.models import Flight
from app.providers.errors import ProviderError

ProviderAccessStatus = Literal["available", "requires_approval", "not_configured", "disabled"]
ImplementationStatus = Literal["implemented", "adapter_only", "planned"]


class DateRange(BaseModel):
    start: date
    end: date


class TripLengthRange(BaseModel):
    minDays: int = 1
    maxDays: int = 30


class SearchConstraints(BaseModel):
    passengers: int = 1
    cabin: str = "economy"
    directOnly: bool = True
    maxStops: int | None = None


class ProviderCapabilities(BaseModel):
    oneWaySearch: bool = False
    returnSearch: bool = False
    multiCityOrOpenJaw: bool = False
    flexibleDateSearch: bool = False
    priceHistory: bool = False
    deepLinks: bool = False
    affiliateLinks: bool = False
    baggageInfo: bool = False
    liveAvailability: bool = False


class ProviderStatus(BaseModel):
    name: str
    accessStatus: ProviderAccessStatus
    enabled: bool
    configured: bool
    implementationStatus: ImplementationStatus
    capabilities: ProviderCapabilities = ProviderCapabilities()
    requiredEnvVars: list[str] = []
    rateLimitNotes: str | None = None
    warnings: list[str] = []


class SmokeTestResult(BaseModel):
    provider: str
    ok: bool = False
    apiOk: bool = False
    enabled: bool = False
    configured: bool = False
    origin: str | None = None
    destination: str | None = None
    departureDate: str | None = None
    rawOffersCount: int = 0
    mappedFlightsCount: int = 0
    skippedOffersCount: int = 0
    deepLinksReturned: int = 0
    affiliateLinkGenerated: bool = False
    sampleFlight: dict[str, Any] | None = None
    warnings: list[str] = []


def sanitize_flight_summary(flight: Flight) -> dict[str, Any]:
    """Safe subset of a flight for diagnostics output. Never raw payloads or links with secrets."""
    return {
        "origin": flight.origin,
        "destination": flight.destination,
        "departureDateTime": flight.departureDateTime.isoformat(),
        "price": flight.price,
        "currency": flight.currency,
        "stops": flight.stops,
        "confidenceLevel": flight.confidenceLevel,
        "deepLinkPresent": bool(flight.deepLink),
        "affiliateLinkPresent": bool(flight.affiliateUrl),
    }


def sample_search_dates(start_date: date, end_date: date, max_dates: int) -> list[date]:
    """Spread a bounded number of candidate departure dates across a range."""
    if end_date < start_date:
        return []
    total_days = (end_date - start_date).days
    step = 1 if total_days <= 14 else 3
    dates: list[date] = []
    current = start_date
    while current <= end_date and len(dates) < max_dates:
        dates.append(current)
        current += timedelta(days=step)
    if end_date not in dates and len(dates) < max_dates:
        dates.append(end_date)
    return dates[:max_dates]


class FlightProvider(ABC):
    """Provider-agnostic flight data source.

    Concrete providers implement `search_flexible` (their natural bulk search) and
    `get_provider_status`. One-way/return searches, smoke tests, and the legacy
    outbound/return search methods used by the trip builder derive from those.
    """

    name: str = "abstract"

    def __init__(self) -> None:
        self.requests_attempted = 0
        self.raw_offers_count = 0
        self.mapped_flights_count = 0
        self.skipped_offers_count = 0
        self.deep_links_returned = 0
        self.affiliate_links_generated = 0
        self.cached_flights_count = 0
        self.warnings: list[str] = []

    @abstractmethod
    def search_flexible(
        self,
        origin_airports: list[str] | None,
        destination_scope: list[str] | None,
        date_range: DateRange,
        trip_length_range: TripLengthRange | None = None,
        constraints: SearchConstraints | None = None,
    ) -> list[Flight]:
        """Search flights from any of the origins to the destination scope.

        `origin_airports=None` means any origin; `destination_scope=None` means anywhere.
        """

    @abstractmethod
    def get_provider_status(self) -> ProviderStatus:
        pass

    def search_one_way(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        passengers: int = 1,
        cabin: str = "economy",
    ) -> list[Flight]:
        return self.search_flexible(
            [origin],
            [destination],
            DateRange(start=departure_date, end=departure_date),
            constraints=SearchConstraints(passengers=passengers, cabin=cabin),
        )

    def search_return(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
        passengers: int = 1,
        cabin: str = "economy",
    ) -> list[Flight]:
        outbound = self.search_one_way(origin, destination, departure_date, passengers, cabin)
        inbound = self.search_one_way(destination, origin, return_date, passengers, cabin)
        return outbound + inbound

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
        if not status.enabled or not status.configured:
            result.warnings.append(f"Provider '{self.name}' is not enabled and configured; smoke test skipped.")
            return result
        try:
            flights = self.search_one_way(origin, destination, departure_date)
        except ProviderError as exc:
            result.warnings.append(str(exc))
            return result
        result.apiOk = True
        result.ok = True
        result.mappedFlightsCount = min(len(flights), max_results) if max_results else len(flights)
        result.deepLinksReturned = sum(1 for flight in flights if flight.deepLink)
        if flights:
            result.sampleFlight = sanitize_flight_summary(flights[0])
        else:
            result.warnings.append("No flights found for the smoke-test route and date.")
        return result

    def normalize_response_to_internal_flights(self, raw_response: Any) -> list[Flight]:
        raise NotImplementedError(f"Provider '{self.name}' has no raw payload to normalize.")

    # Legacy search surface used by FlightSearchService and the trip builder.
    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.search_flexible(
            origin_codes,
            destination_codes,
            DateRange(start=start_date, end=end_date),
            constraints=SearchConstraints(directOnly=direct_only),
        )

    def search_outbound_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.search_flexible(
            origin_codes,
            None,
            DateRange(start=start_date, end=end_date),
            constraints=SearchConstraints(directOnly=direct_only),
        )

    def search_return_flights(
        self,
        return_destination_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.search_flexible(
            None,
            return_destination_codes,
            DateRange(start=start_date, end=end_date),
            constraints=SearchConstraints(directOnly=direct_only),
        )
