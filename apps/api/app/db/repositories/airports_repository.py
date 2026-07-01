from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import AirportDB
from app.models import Airport


class AirportsRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_airports(self) -> list[Airport]:
        rows = self.db.scalars(
            select(AirportDB).options(joinedload(AirportDB.area)).order_by(AirportDB.code)
        ).all()
        return [self._to_schema(row) for row in rows]

    def get_airport(self, code: str) -> Airport | None:
        row = self.db.scalar(
            select(AirportDB).options(joinedload(AirportDB.area)).where(AirportDB.code == code.upper())
        )
        return self._to_schema(row) if row else None

    def list_origin_candidates(self) -> list[Airport]:
        rows = self.db.scalars(
            select(AirportDB)
            .options(joinedload(AirportDB.area))
            .where(AirportDB.is_user_origin_candidate.is_(True))
            .order_by(AirportDB.code)
        ).all()
        return [self._to_schema(row) for row in rows]

    @staticmethod
    def _to_schema(row: AirportDB) -> Airport:
        return Airport(
            code=row.code,
            name=row.name,
            city=row.city,
            country=row.country,
            latitude=row.latitude,
            longitude=row.longitude,
            isUserOriginCandidate=row.is_user_origin_candidate,
            areaSlug=row.area.slug if row.area else None,
            areaName=row.area.name if row.area else None,
        )
