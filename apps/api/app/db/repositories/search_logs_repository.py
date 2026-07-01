from sqlalchemy.orm import Session

from app.db.models import SearchLogDB
from app.models import TripSearchRequest


class SearchLogsRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_search_log(self, request: TripSearchRequest, result_count: int) -> None:
        self.db.add(
            SearchLogDB(
                origin_airports=request.originAirports,
                start_date=request.startDate,
                end_date=request.endDate,
                min_trip_length_days=request.minTripLengthDays,
                max_trip_length_days=request.maxTripLengthDays,
                max_budget=request.maxBudget,
                max_ground_transfer_hours=request.maxGroundTransferHours,
                trip_style=request.tripStyle,
                result_count=result_count,
            )
        )
