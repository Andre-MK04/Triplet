from abc import ABC, abstractmethod
from datetime import date

from app.models import Flight


class FlightProvider(ABC):
    @abstractmethod
    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
        direct_only: bool = True,
    ) -> list[Flight]:
        pass

    @abstractmethod
    def search_outbound_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        pass

    @abstractmethod
    def search_return_flights(
        self,
        return_destination_codes: list[str],
        start_date: date,
        end_date: date,
        direct_only: bool = True,
    ) -> list[Flight]:
        pass
