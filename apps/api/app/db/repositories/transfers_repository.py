from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AirportDB, GroundTransferDB
from app.models import GroundTransfer


class TransfersRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_transfers(self) -> list[GroundTransfer]:
        rows = self.db.scalars(select(GroundTransferDB).order_by(GroundTransferDB.from_airport_code)).all()
        return [self._to_schema(row) for row in rows]

    def get_transfer(self, from_airport_code: str, to_airport_code: str) -> GroundTransfer | None:
        row = self.db.scalar(
            select(GroundTransferDB)
            .where(GroundTransferDB.from_airport_code == from_airport_code.upper())
            .where(GroundTransferDB.to_airport_code == to_airport_code.upper())
        )
        return self._to_schema(row) if row else None

    def find_transfer_between_areas_or_airports(
        self,
        from_airport_code: str,
        to_airport_code: str,
    ) -> GroundTransfer | None:
        exact = self.get_transfer(from_airport_code, to_airport_code)
        if exact:
            return exact

        from_airport = self.db.get(AirportDB, from_airport_code.upper())
        to_airport = self.db.get(AirportDB, to_airport_code.upper())
        if not from_airport or not to_airport:
            return None

        rows = self.db.scalars(select(GroundTransferDB)).all()
        for row in rows:
            transfer_from = self.db.get(AirportDB, row.from_airport_code)
            transfer_to = self.db.get(AirportDB, row.to_airport_code)
            if (
                transfer_from
                and transfer_to
                and transfer_from.area_id == from_airport.area_id
                and transfer_to.area_id == to_airport.area_id
            ):
                return self._to_schema(row)
        return None

    @staticmethod
    def _to_schema(row: GroundTransferDB) -> GroundTransfer:
        return GroundTransfer(
            fromAirport=row.from_airport_code,
            toAirport=row.to_airport_code,
            fromCity=row.from_city,
            toCity=row.to_city,
            durationHours=row.duration_hours,
            estimatedCost=row.estimated_cost,
            mode=row.mode,
        )
