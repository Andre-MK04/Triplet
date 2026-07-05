from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import TripSuggestionDB
from app.models import TripOption

# Suggestions built from cached/demo fares go stale quickly; keep links working for a week.
SUGGESTION_TTL_DAYS = 7


class TripSuggestionsRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_trips(
        self,
        trips: list[TripOption],
        user_id: str | None = None,
        saved_search_id: str | None = None,
        commit: bool = True,
    ) -> None:
        """Persist trips and stamp each TripOption with its suggestionId."""
        for trip in trips:
            suggestion_id = str(uuid4())
            self.db.add(
                TripSuggestionDB(
                    id=suggestion_id,
                    user_id=user_id,
                    saved_search_id=saved_search_id,
                    title=build_title(trip),
                    trip_type=trip.tripType,
                    origin_airport=trip.outboundFlight.origin,
                    outbound_destination=trip.outboundFlight.destination,
                    return_origin=trip.returnFlight.origin if trip.tripType == "open_jaw" else None,
                    final_arrival_airport=trip.returnFlight.destination,
                    start_date=trip.outboundFlight.departureDateTime.date(),
                    end_date=trip.returnFlight.departureDateTime.date(),
                    nights=trip.nights,
                    total_price=trip.totalPrice,
                    currency=trip.outboundFlight.currency,
                    deal_score=trip.dealScore,
                    fit_score=trip.fitScore,
                    payload=trip.model_dump(mode="json"),
                    expires_at=datetime.utcnow() + timedelta(days=SUGGESTION_TTL_DAYS),
                )
            )
            trip.suggestionId = suggestion_id
        if trips and commit:
            self.db.commit()

    def get_visible(self, suggestion_id: str, user_id: str | None = None) -> TripSuggestionDB | None:
        """Anonymous suggestions are visible to anyone with the link; user-owned ones only to the owner."""
        row = self.db.get(TripSuggestionDB, suggestion_id)
        if not row:
            return None
        if row.user_id is not None and row.user_id != user_id:
            return None
        return row


def build_title(trip: TripOption) -> str:
    if trip.tripType == "open_jaw":
        return (
            f"{trip.outboundFlight.origin} → {trip.outboundFlight.destination} / "
            f"{trip.returnFlight.origin} → {trip.returnFlight.destination}"
        )
    return f"{trip.outboundFlight.origin} → {trip.outboundFlight.destination} return"
