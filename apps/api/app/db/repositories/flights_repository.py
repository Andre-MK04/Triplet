from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FlightDB
from app.models import Flight


class FlightsRepository:
    def __init__(self, db: Session):
        self.db = db

    def search_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
    ) -> list[Flight]:
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        normalized_origins = [code.upper() for code in origin_codes]
        query = (
            select(FlightDB)
            .where(FlightDB.origin_code.in_(normalized_origins))
            .where(FlightDB.departure_datetime >= start_dt)
            .where(FlightDB.departure_datetime <= end_dt)
        )
        if destination_codes:
            normalized_destinations = [code.upper() for code in destination_codes]
            query = query.where(FlightDB.destination_code.in_(normalized_destinations))

        rows = self.db.scalars(query.order_by(FlightDB.departure_datetime, FlightDB.price)).all()
        return [self._to_schema(row) for row in rows]

    def search_flights_between_dates(self, start_date: date, end_date: date) -> list[Flight]:
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        rows = self.db.scalars(
            select(FlightDB)
            .where(FlightDB.departure_datetime >= start_dt)
            .where(FlightDB.departure_datetime <= end_dt)
            .order_by(FlightDB.departure_datetime, FlightDB.price)
        ).all()
        return [self._to_schema(row) for row in rows]

    def search_outbound_flights(self, origin_codes: list[str], start_date: date, end_date: date) -> list[Flight]:
        return self.search_flights(origin_codes, start_date, end_date)

    def search_return_flights(self, origin_destination_codes: list[str], start_date: date, end_date: date) -> list[Flight]:
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        normalized_codes = [code.upper() for code in origin_destination_codes]
        rows = self.db.scalars(
            select(FlightDB)
            .where(FlightDB.destination_code.in_(normalized_codes))
            .where(FlightDB.departure_datetime >= start_dt)
            .where(FlightDB.departure_datetime <= end_dt)
            .order_by(FlightDB.departure_datetime, FlightDB.price)
        ).all()
        return [self._to_schema(row) for row in rows]

    def list_all_mock_flights(self) -> list[Flight]:
        rows = self.db.scalars(
            select(FlightDB).where(FlightDB.provider == "mock").order_by(FlightDB.id)
        ).all()
        return [self._to_schema(row) for row in rows]

    def get_cached_flights(
        self,
        origin_codes: list[str],
        start_date: date,
        end_date: date,
        destination_codes: list[str] | None = None,
    ) -> list[Flight]:
        return self.search_flights(origin_codes, start_date, end_date, destination_codes)

    def upsert_flight(self, flight: Flight) -> None:
        row = self.db.get(FlightDB, flight.id)
        if not row:
            row = FlightDB(id=flight.id)
            self.db.add(row)

        row.origin_code = flight.origin
        row.destination_code = flight.destination
        row.departure_datetime = flight.departureDateTime
        row.arrival_datetime = flight.arrivalDateTime
        row.airline = flight.airline
        row.price = flight.price
        row.currency = flight.currency
        row.booking_url = flight.bookingUrl
        row.baggage_included = flight.baggageIncluded
        row.provider = flight.provider
        row.observed_at = datetime.utcnow()
        row.provider_offer_id = flight.providerOfferId
        row.deep_link = flight.deepLink
        row.agent_name = flight.agentName
        row.stops = flight.stops
        row.duration_minutes = flight.durationMinutes
        row.is_live = flight.isLive
        row.expires_at = datetime.utcnow() + timedelta(hours=6) if flight.isLive else None

    def upsert_flights(self, flights: list[Flight]) -> None:
        for flight in flights:
            self.upsert_flight(flight)
        self.db.commit()

    @staticmethod
    def _to_schema(row: FlightDB) -> Flight:
        return Flight(
            id=row.id,
            origin=row.origin_code,
            destination=row.destination_code,
            departureDateTime=row.departure_datetime,
            arrivalDateTime=row.arrival_datetime,
            airline=row.airline,
            price=row.price,
            currency=row.currency,
            bookingUrl=row.booking_url,
            baggageIncluded=row.baggage_included,
            provider=row.provider,
            providerOfferId=row.provider_offer_id,
            deepLink=row.deep_link,
            agentName=row.agent_name,
            stops=row.stops,
            durationMinutes=row.duration_minutes,
            isLive=row.is_live,
        )
