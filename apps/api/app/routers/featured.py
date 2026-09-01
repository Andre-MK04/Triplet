"""The homepage deal board.

Cheap by construction: one indexed read of a snapshot the scheduler built. No
provider call, no ranking work, nothing that scales with traffic.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deals.featured import board_is_stale, featured_origins, latest_snapshot
from app.models import TripOption
from app.security import RateLimitCategory, check_rate_limit

router = APIRouter(tags=["featured"])


class FeaturedDealsResponse(BaseModel):
    trips: list[TripOption]
    #: When Triplet last assembled this board. NOT the age of any fare in it —
    #: each trip carries its own observation time, and the interface must keep
    #: the two apart.
    generatedAt: datetime | None = None
    originAirports: list[str]
    #: True when the board is older than expected, so the page can say so
    #: rather than implying it was just refreshed.
    isStale: bool = False
    #: True before the scheduler has ever run, so the page shows its own empty
    #: state instead of pretending there are no cheap fares anywhere.
    isReady: bool = True


@router.get("/featured-deals", response_model=FeaturedDealsResponse)
def get_featured_deals(
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> FeaturedDealsResponse:
    check_rate_limit(RateLimitCategory.CHEAP, http_request)

    try:
        snapshot = latest_snapshot(db)
    except SQLAlchemyError:
        db.rollback()
        # The homepage should render without its board rather than fail.
        return FeaturedDealsResponse(trips=[], originAirports=featured_origins(), isReady=False)

    if snapshot is None:
        return FeaturedDealsResponse(trips=[], originAirports=featured_origins(), isReady=False)

    # Everyone gets the same board, so it is worth caching at the edge. Short
    # enough that a refresh reaches visitors promptly, with stale-while-
    # revalidate so nobody waits on a rebuild.
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=3600"

    return FeaturedDealsResponse(
        trips=[TripOption.model_validate(trip) for trip in snapshot.trips],
        generatedAt=snapshot.generated_at,
        originAirports=list(snapshot.origin_airports or featured_origins()),
        isStale=board_is_stale(snapshot),
        isReady=True,
    )
