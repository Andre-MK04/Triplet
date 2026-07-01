from datetime import date

from sqlalchemy.orm import Session

from app.db.repositories.flights_repository import FlightsRepository
from app.models import Flight
from app.providers.flight_provider import FlightProvider


class DatabaseFlightProvider(FlightProvider):
    def __init__(self, db: Session):
        self.repository = FlightsRepository(db)

    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.repository.search_flights(
            origin_codes=origin_codes,
            start_date=start_date,
            end_date=end_date,
            destination_codes=destination_codes,
        )

    def search_outbound_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.repository.search_outbound_flights(origin_codes, start_date, end_date)

    def search_return_flights(
        self,
        return_destination_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.repository.search_return_flights(return_destination_codes, start_date, end_date)
