"""Collecting travellers' reports on whether an observed fare still held.

Anonymous by design: no user is attached, no address is stored, and the only
identifier is a random per-click value whose sole job is to stop one check being
answered twice.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.observability import events
from app.pricing.reliability import (
    VALID_AGE_BUCKETS,
    VALID_RESPONSES,
    record_feedback,
)
from app.security import RateLimitCategory, check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fare-feedback", tags=["fare-feedback"])


class FareFeedbackRequest(BaseModel):
    """One traveller's answer about one fare they checked.

    Everything here describes the fare. Nothing describes the person, and the
    schema is closed so a client cannot smuggle extra fields into the record.
    """

    model_config = {"extra": "forbid"}

    checkId: str = Field(min_length=8, max_length=64)
    origin: str = Field(min_length=2, max_length=8)
    destination: str = Field(min_length=2, max_length=8)
    tripType: str = Field(max_length=20)
    fareKind: str = Field(max_length=32)
    fareAgeBucket: str = Field(max_length=16)
    shownPrice: float = Field(gt=0, le=1_000_000)
    response: str = Field(max_length=24)
    currency: str = Field(default="EUR", max_length=8)
    provider: str | None = Field(default=None, max_length=40)


class FareFeedbackResponse(BaseModel):
    recorded: bool


@router.post("", response_model=FareFeedbackResponse)
def submit_fare_feedback(
    request: FareFeedbackRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> FareFeedbackResponse:
    check_rate_limit(RateLimitCategory.CHEAP, http_request)

    if request.response not in VALID_RESPONSES:
        raise HTTPException(status_code=400, detail="Unknown feedback response.")
    if request.fareAgeBucket not in VALID_AGE_BUCKETS:
        raise HTTPException(status_code=400, detail="Unknown fare age bucket.")

    try:
        recorded = record_feedback(
            db,
            check_id=request.checkId,
            origin=request.origin,
            destination=request.destination,
            trip_type=request.tripType,
            fare_kind=request.fareKind,
            fare_age_bucket=request.fareAgeBucket,
            shown_price=request.shownPrice,
            response=request.response,
            currency=request.currency,
            provider=request.provider,
        )
    except SQLAlchemyError:
        db.rollback()
        # Losing one voluntary answer is not worth showing anyone an error.
        logger.exception("fare_feedback_store_failed")
        return FareFeedbackResponse(recorded=False)

    if recorded:
        events.fare_feedback_received(
            response=request.response,
            age_bucket=request.fareAgeBucket,
            fare_kind=request.fareKind,
        )
    # `recorded=False` for an already-answered check is not an error: the client
    # should stop asking either way, which is exactly what it does.
    return FareFeedbackResponse(recorded=recorded)
