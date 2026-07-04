from sqlalchemy.orm import Session

from app.db.repositories.flights_repository import FlightsRepository
from app.models import Flight
from app.providers.flight_provider import (
    DateRange,
    FlightProvider,
    ProviderCapabilities,
    ProviderStatus,
    SearchConstraints,
    TripLengthRange,
)


class DatabaseFlightProvider(FlightProvider):
    """Serves seeded demo fares and fares cached from live providers. Never live prices."""

    name = "database"

    def __init__(self, db: Session):
        super().__init__()
        self.repository = FlightsRepository(db)

    def search_flexible(
        self,
        origin_airports: list[str] | None,
        destination_scope: list[str] | None,
        date_range: DateRange,
        trip_length_range: TripLengthRange | None = None,
        constraints: SearchConstraints | None = None,
    ) -> list[Flight]:
        if origin_airports:
            return self.repository.search_flights(
                origin_codes=origin_airports,
                start_date=date_range.start,
                end_date=date_range.end,
                destination_codes=destination_scope,
            )
        if destination_scope:
            return self.repository.search_return_flights(destination_scope, date_range.start, date_range.end)
        return self.repository.search_flights_between_dates(date_range.start, date_range.end)

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
                priceHistory=True,
                deepLinks=True,
            ),
            requiredEnvVars=["DATABASE_URL"],
            rateLimitNotes="Local database reads; serves cached/demo fares only.",
        )
