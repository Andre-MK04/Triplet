import hashlib
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PriceObservationDB
from app.models import Flight

# Confidence levels worth keeping as price history. Cached rows re-read from our own
# database and mock/demo fares would only pollute the baseline.
OBSERVABLE_CONFIDENCE_LEVELS = {"live", "indicative"}
DUPLICATE_WINDOW_HOURS = 1


class PriceObservationsRepository:
    def __init__(self, db: Session):
        self.db = db

    def record_flights(self, flights: list[Flight], commit: bool = True) -> int:
        recorded = 0
        for flight in flights:
            if flight.confidenceLevel not in OBSERVABLE_CONFIDENCE_LEVELS:
                continue
            if flight.price <= 0:
                continue
            if self._record_flight(flight):
                recorded += 1
        if recorded and commit:
            self.db.commit()
        return recorded

    def _record_flight(self, flight: Flight) -> bool:
        raw_hash = observation_hash(flight)
        window_start = datetime.utcnow() - timedelta(hours=DUPLICATE_WINDOW_HOURS)
        duplicate = self.db.scalar(
            select(PriceObservationDB.id)
            .where(PriceObservationDB.raw_hash == raw_hash)
            .where(PriceObservationDB.observed_at >= window_start)
            .limit(1)
        )
        if duplicate:
            return False
        self.db.add(
            PriceObservationDB(
                provider=flight.provider,
                origin_code=flight.origin,
                destination_code=flight.destination,
                departure_date=flight.departureDateTime.date(),
                observed_price=flight.price,
                currency=flight.currency,
                observed_at=flight.observedAt or datetime.utcnow(),
                confidence=flight.confidenceLevel,
                link_available=bool(flight.deepLink or flight.affiliateUrl or flight.bookingUrl),
                raw_hash=raw_hash,
            )
        )
        return True

    def route_stats(
        self,
        origin: str,
        destination: str,
        lookback_days: int = 90,
    ) -> dict:
        """Min/avg/count of observed prices for a route, for baseline comparisons."""
        window_start = datetime.utcnow() - timedelta(days=lookback_days)
        row = self.db.execute(
            select(
                func.count(PriceObservationDB.id),
                func.min(PriceObservationDB.observed_price),
                func.avg(PriceObservationDB.observed_price),
            )
            .where(PriceObservationDB.origin_code == origin.upper())
            .where(PriceObservationDB.destination_code == destination.upper())
            .where(PriceObservationDB.observed_at >= window_start)
        ).one()
        count, min_price, avg_price = row
        return {
            "count": int(count or 0),
            "minPrice": float(min_price) if min_price is not None else None,
            "avgPrice": round(float(avg_price), 2) if avg_price is not None else None,
        }

    def observations_for_route(
        self,
        origin: str,
        destination: str,
        departure_date: date | None = None,
        limit: int = 100,
    ) -> list[PriceObservationDB]:
        query = (
            select(PriceObservationDB)
            .where(PriceObservationDB.origin_code == origin.upper())
            .where(PriceObservationDB.destination_code == destination.upper())
            .order_by(PriceObservationDB.observed_at.desc())
            .limit(limit)
        )
        if departure_date:
            query = query.where(PriceObservationDB.departure_date == departure_date)
        return list(self.db.scalars(query))


def observation_hash(flight: Flight) -> str:
    key = "|".join(
        [
            flight.provider,
            flight.origin,
            flight.destination,
            flight.departureDateTime.date().isoformat(),
            f"{flight.price:.2f}",
            flight.currency,
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()
