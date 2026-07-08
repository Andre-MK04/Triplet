from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import CachedRoundTripDB
from app.providers.travelpayouts.mapper import RoundTripFare

# How long a cached deal is considered fresh enough to serve without re-fetching.
DEFAULT_TTL_HOURS = 24


class CachedDealsRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_deals(self, fares: list[RoundTripFare], ttl_hours: int = DEFAULT_TTL_HOURS) -> int:
        """Insert/refresh cached deals. Dedup on route+dates, keep the cheapest.

        Returns the number of rows written (inserted or updated).
        """
        now = datetime.utcnow()
        expires = now + timedelta(hours=ttl_hours)
        written = 0
        for fare in fares:
            departure = _parse_date(fare.departureDate)
            if not departure:
                continue
            return_date = _parse_date(fare.returnDate)
            row = self.db.scalar(
                select(CachedRoundTripDB)
                .where(CachedRoundTripDB.origin_code == fare.origin.upper())
                .where(CachedRoundTripDB.destination_code == fare.destination.upper())
                .where(CachedRoundTripDB.departure_date == departure)
                .where(CachedRoundTripDB.return_date == return_date)
            )
            if row and row.price <= fare.price:
                # Keep the cheaper existing price but refresh its freshness stamp.
                row.observed_at = now
                row.expires_at = expires
                written += 1
                continue
            if not row:
                row = CachedRoundTripDB(
                    origin_code=fare.origin.upper(),
                    destination_code=fare.destination.upper(),
                    departure_date=departure,
                    return_date=return_date,
                )
                self.db.add(row)
            row.price = fare.price
            row.currency = fare.currency
            row.airline = fare.airline
            row.stops = fare.stops
            row.booking_url = fare.bookingUrl
            row.affiliate_url = fare.affiliateUrl
            row.observed_at = now
            row.expires_at = expires
            written += 1
        self.db.commit()
        return written

    def fresh_deals(self, origins: list[str], ttl_hours: int = DEFAULT_TTL_HOURS) -> list[RoundTripFare]:
        """Cached deals from these origins that are still fresh, as RoundTripFares."""
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        codes = [code.upper() for code in origins]
        rows = self.db.scalars(
            select(CachedRoundTripDB)
            .where(CachedRoundTripDB.origin_code.in_(codes))
            .where(CachedRoundTripDB.observed_at >= cutoff)
            .order_by(CachedRoundTripDB.price)
        ).all()
        return [_to_fare(row) for row in rows]

    def has_fresh(self, origins: list[str], ttl_hours: int = DEFAULT_TTL_HOURS) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        codes = [code.upper() for code in origins]
        return (
            self.db.scalar(
                select(CachedRoundTripDB.id)
                .where(CachedRoundTripDB.origin_code.in_(codes))
                .where(CachedRoundTripDB.observed_at >= cutoff)
                .limit(1)
            )
            is not None
        )

    def prune_stale(self, ttl_hours: int = DEFAULT_TTL_HOURS) -> int:
        """Delete deals older than the freshness window. Returns rows deleted."""
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        result = self.db.execute(delete(CachedRoundTripDB).where(CachedRoundTripDB.observed_at < cutoff))
        self.db.commit()
        return result.rowcount or 0


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _to_fare(row: CachedRoundTripDB) -> RoundTripFare:
    return RoundTripFare(
        origin=row.origin_code,
        destination=row.destination_code,
        price=row.price,
        currency=row.currency,
        departureDate=row.departure_date.isoformat(),
        returnDate=row.return_date.isoformat() if row.return_date else None,
        airline=row.airline,
        stops=row.stops,
        bookingUrl=row.booking_url,
        affiliateUrl=row.affiliate_url,
    )
