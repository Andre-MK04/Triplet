from datetime import date

from app.models import Flight
from app.providers.flight_provider import FlightProvider


class MockFlightProvider(FlightProvider):
    def __init__(self, flights: list[Flight]):
        self.flights = flights

    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
        direct_only: bool = True,
    ) -> list[Flight]:
        origins = {code.upper() for code in origin_codes}
        destinations = {code.upper() for code in destination_codes} if destination_codes else None
        return [
            flight
            for flight in self.flights
            if flight.origin in origins
            and start_date <= flight.departureDateTime.date() <= end_date
            and (destinations is None or flight.destination in destinations)
        ]

    def search_outbound_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        return self.search_flights(origin_codes, start_date, end_date)

    def search_return_flights(
        self,
        return_destination_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        destinations = {code.upper() for code in return_destination_codes}
        return [
            flight
            for flight in self.flights
            if flight.destination in destinations
            and start_date <= flight.departureDateTime.date() <= end_date
        ]
