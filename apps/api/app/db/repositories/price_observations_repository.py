"""Reading and writing Triplet's fare-observation history.

Writes are batched and deduplicated: a discovery search can produce hundreds of
fares, and doing a lookup-then-insert per fare would add hundreds of round trips
to a request the traveller is waiting on.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PriceObservationDB
from app.models import Flight
from app.pricing.observation import FareObservation

# Confidence levels worth keeping as price history. Rows re-read from our own
# database and mock/demo fares would only pollute the baseline.
OBSERVABLE_CONFIDENCE_LEVELS = {"live", "indicative"}
# Statistics are drawn from what the provider actually reported, never from
# totals Triplet assembled itself.
PROVIDER_KINDS = ("cached_provider", "live_provider")


class PriceObservationsRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------- writing

    def record_observations(self, observations: list[FareObservation], commit: bool = True) -> int:
        """Store price events we have not already seen. Returns how many were new.

        One SELECT for the whole batch, then one INSERT per genuinely new event.
        The unique constraint on the identity hash is the real guarantee; this
        check just avoids provoking it for the common case.
        """
        valid = [row for row in observations if row.is_valid()]
        if not valid:
            return 0

        by_identity: dict[str, FareObservation] = {row.identity(): row for row in valid}
        known = set(
            self.db.scalars(
                select(PriceObservationDB.raw_hash).where(
                    PriceObservationDB.raw_hash.in_(list(by_identity))
                )
            )
        )

        fresh = [
            PriceObservationDB(
                provider=row.provider,
                observation_kind=row.kind,
                trip_type=row.trip_type,
                origin_code=row.origin.upper(),
                destination_code=row.destination.upper(),
                departure_date=row.departure_date,
                return_date=row.return_date,
                nights=row.nights,
                observed_price=row.price,
                currency=row.currency.upper(),
                found_at=row.found_at,
                observed_at=row.observed_at or datetime.utcnow(),
                stops=row.stops,
                airline=row.airline,
                confidence=row.confidence,
                link_available=row.link_available,
                raw_hash=identity,
            )
            for identity, row in by_identity.items()
            if identity not in known
        ]
        if not fresh:
            return 0
        self.db.add_all(fresh)
        if commit:
            self.db.commit()
        return len(fresh)

    def record_flights(self, flights: list[Flight], commit: bool = True) -> int:
        """Record one-way candidate fares returned by a provider search."""
        return self.record_observations(
            [
                FareObservation(
                    origin=flight.origin,
                    destination=flight.destination,
                    departure_date=flight.departureDateTime.date(),
                    price=flight.price,
                    currency=flight.currency,
                    provider=flight.provider,
                    trip_type="one_way",
                    found_at=flight.observedAt,
                    stops=flight.stops,
                    airline=flight.airline,
                    confidence=flight.confidenceLevel,
                    link_available=bool(flight.deepLink or flight.affiliateUrl or flight.bookingUrl),
                )
                for flight in flights
                if flight.confidenceLevel in OBSERVABLE_CONFIDENCE_LEVELS and flight.price > 0
            ],
            commit=commit,
        )

    # ---------------------------------------------------------------- reading

    def comparable_prices(
        self,
        origin: str,
        destination: str,
        trip_type: str,
        departure_from: date | None = None,
        departure_to: date | None = None,
        nights_range: tuple[int, int] | None = None,
        direct_only: bool | None = None,
        limit: int = 600,
    ) -> list[float]:
        """Observed prices for one route, narrowed by whatever the caller can.

        Only genuine provider observations count: a composite estimate is
        Triplet's own arithmetic and would be circular evidence about its own
        pricing.
        """
        query = (
            select(PriceObservationDB.observed_price)
            .where(PriceObservationDB.origin_code == origin.upper())
            .where(PriceObservationDB.destination_code == destination.upper())
            .where(PriceObservationDB.trip_type == trip_type)
            .where(PriceObservationDB.observation_kind.in_(PROVIDER_KINDS))
        )
        if departure_from:
            query = query.where(PriceObservationDB.departure_date >= departure_from)
        if departure_to:
            query = query.where(PriceObservationDB.departure_date <= departure_to)
        if nights_range:
            low, high = nights_range
            query = query.where(PriceObservationDB.nights.between(low, high))
        if direct_only is True:
            query = query.where(PriceObservationDB.stops == 0)
        elif direct_only is False:
            query = query.where(PriceObservationDB.stops > 0)
        return [float(value) for value in self.db.scalars(query.limit(limit))]

    def route_observations(
        self,
        routes: list[tuple[str, str, str]],
        limit_per_route: int = 800,
    ) -> dict[tuple[str, str, str], list[tuple[float, date, int | None, int | None]]]:
        """Every provider observation for a set of (origin, destination, trip type).

        One query for the whole result page rather than one per card: a fifty-row
        search would otherwise issue fifty history lookups on the request the
        traveller is waiting on. Narrowing to similar dates and trip lengths then
        happens in memory, over rows already fetched.
        """
        if not routes:
            return {}
        wanted = {(origin.upper(), destination.upper(), trip) for origin, destination, trip in routes}
        origins = {origin for origin, _, _ in wanted}
        destinations = {destination for _, destination, _ in wanted}
        trip_types = {trip for _, _, trip in wanted}

        rows = self.db.execute(
            select(
                PriceObservationDB.origin_code,
                PriceObservationDB.destination_code,
                PriceObservationDB.trip_type,
                PriceObservationDB.observed_price,
                PriceObservationDB.departure_date,
                PriceObservationDB.nights,
                PriceObservationDB.stops,
            )
            .where(PriceObservationDB.origin_code.in_(origins))
            .where(PriceObservationDB.destination_code.in_(destinations))
            .where(PriceObservationDB.trip_type.in_(trip_types))
            .where(PriceObservationDB.observation_kind.in_(PROVIDER_KINDS))
            .limit(limit_per_route * max(1, len(wanted)))
        ).all()

        grouped: dict[tuple[str, str, str], list[tuple[float, date, int | None, int | None]]] = {}
        for origin, destination, trip, price, departure, nights, stops in rows:
            key = (origin, destination, trip)
            if key not in wanted:
                continue
            grouped.setdefault(key, []).append((float(price), departure, nights, stops))
        return grouped

    def route_stats(self, origin: str, destination: str, lookback_days: int = 90) -> dict:
        """Min/avg/count for a route — the long-standing baseline used in scoring."""
        window_start = datetime.utcnow() - timedelta(days=lookback_days)
        count, min_price, avg_price = self.db.execute(
            select(
                func.count(PriceObservationDB.id),
                func.min(PriceObservationDB.observed_price),
                func.avg(PriceObservationDB.observed_price),
            )
            .where(PriceObservationDB.origin_code == origin.upper())
            .where(PriceObservationDB.destination_code == destination.upper())
            .where(PriceObservationDB.observed_at >= window_start)
        ).one()
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
