from app.models import Flight
from app.providers.flight_provider import (
    DateRange,
    FlightProvider,
    ProviderCapabilities,
    ProviderStatus,
    SearchConstraints,
    TripLengthRange,
)


class MockFlightProvider(FlightProvider):
    name = "mock"

    def __init__(self, flights: list[Flight]):
        super().__init__()
        self.flights = flights

    def search_flexible(
        self,
        origin_airports: list[str] | None,
        destination_scope: list[str] | None,
        date_range: DateRange,
        trip_length_range: TripLengthRange | None = None,
        constraints: SearchConstraints | None = None,
    ) -> list[Flight]:
        origins = {code.upper() for code in origin_airports} if origin_airports else None
        destinations = {code.upper() for code in destination_scope} if destination_scope else None
        return [
            flight
            for flight in self.flights
            if (origins is None or flight.origin in origins)
            and (destinations is None or flight.destination in destinations)
            and date_range.start <= flight.departureDateTime.date() <= date_range.end
        ]

    def get_provider_status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            accessStatus="available",
            enabled=True,
            configured=True,
            implementationStatus="implemented",
            capabilities=ProviderCapabilities(
                oneWaySearch=True,
                returnSearch=True,
                multiCityOrOpenJaw=False,
                flexibleDateSearch=True,
            ),
            rateLimitNotes="In-memory only; no external calls.",
        )
