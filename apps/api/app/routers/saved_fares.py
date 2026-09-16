"""Private bookmarks for fare observations; these do not schedule monitoring."""

from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4
from pydantic import ValidationError

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_required
from app.database import get_db
from app.db.models import SavedFareDB, UserDB
from app.db.repositories.trip_suggestions_repository import TripSuggestionsRepository
from app.security import RateLimitCategory, check_rate_limit
from app.models import TripOption

router = APIRouter(prefix="/me/saved-fares", tags=["saved-fares"])
MAX_SAVED_FARES = 100


def _response(row: SavedFareDB) -> dict:
    return {
        "id": row.id,
        "suggestionId": row.suggestion_id,
        "title": row.title,
        "tripType": row.trip_type,
        "observedPrice": row.price,
        "currency": row.currency,
        "fareStatus": row.fare_status,
        "observedAt": row.observed_at,
        "checkPriceUrl": row.check_price_url,
        "savedAt": row.created_at,
        "trip": row.itinerary_snapshot,
        "disclaimer": (
            "Saved fare is an observation, not a reserved or monitored price. "
            + ("Check each flight separately using the saved route; ground travel is estimated."
               if row.trip_type in {"multi_city", "open_jaw"} else "Check the final price with the provider.")
        ),
    }


@router.get("")
def list_saved_fares(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> list[dict]:
    rows = db.scalars(
        select(SavedFareDB).where(SavedFareDB.user_id == user.id)
        .order_by(SavedFareDB.created_at.desc()).limit(MAX_SAVED_FARES)
    ).all()
    return [_response(row) for row in rows]


@router.post("/{suggestion_id}")
def save_fare(
    suggestion_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> dict:
    check_rate_limit(RateLimitCategory.CHEAP, request, user.id)
    if len(suggestion_id) > 36:
        raise HTTPException(status_code=404, detail="Trip suggestion not found.")
    existing = db.scalar(select(SavedFareDB).where(
        SavedFareDB.user_id == user.id, SavedFareDB.suggestion_id == suggestion_id,
    ))
    if existing:
        return _response(existing)
    suggestion = TripSuggestionsRepository(db).get_visible(suggestion_id, user_id=user.id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Trip suggestion not found or expired.")
    count = db.scalar(select(func.count()).select_from(SavedFareDB).where(SavedFareDB.user_id == user.id)) or 0
    if count >= MAX_SAVED_FARES:
        raise HTTPException(status_code=409, detail="You have reached your saved fare limit. Remove one to save another.")

    # Only selected typed fields from an internally persisted suggestion cross
    # this boundary. Never store raw provider payload or a URL supplied by a client.
    trip = suggestion.payload
    snapshot = None
    try:
        normalized = TripOption.model_validate(trip)
        normalized.suggestionId = suggestion_id
        snapshot = normalized.model_dump(mode="json")
        # Reject unsafe links even if an older internal suggestion stored one.
        snapshot = _sanitize_snapshot_links(snapshot)
    except ValidationError:
        # Legacy suggestions can still be bookmarked, but the response makes
        # missing itinerary detail explicit rather than inventing it.
        snapshot = None
    outbound = trip.get("outboundFlight") or {}
    price_info = trip.get("price") or {}
    confidence = outbound.get("confidenceLevel")
    fare_status = (
        "demo" if confidence == "mock" else
        "estimated" if price_info.get("isEstimate") else
        "live" if price_info.get("isLive") and confidence == "live" else
        "cached" if confidence == "cached" else "indicative"
    )
    observed_text = outbound.get("observedAt")
    try:
        observed = datetime.fromisoformat(observed_text.replace("Z", "+00:00")) if observed_text else suggestion.created_at
        if observed.tzinfo is not None:
            observed = observed.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, AttributeError):
        observed = suggestion.created_at
    link = next((value for value in (
        trip.get("bookingUrl"), outbound.get("bookingUrl"), outbound.get("deepLink"), outbound.get("affiliateUrl"),
    ) if isinstance(value, str) and len(value) <= 1000 and _safe_link(value)), None)
    if suggestion.trip_type in {"multi_city", "open_jaw"}:
        link = None # There is no single quote/link for separately observed legs.
    row = SavedFareDB(
        id=str(uuid4()), user_id=user.id, suggestion_id=suggestion_id,
        title=suggestion.title, trip_type=suggestion.trip_type,
        price=suggestion.total_price, currency=suggestion.currency,
        fare_status=fare_status,
        observed_at=observed, check_price_url=link,
        itinerary_snapshot=snapshot,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        # Two taps/devices may race after the initial lookup. The unique
        # user/suggestion constraint makes saving idempotent across that race.
        existing = db.scalar(select(SavedFareDB).where(
            SavedFareDB.user_id == user.id, SavedFareDB.suggestion_id == suggestion_id,
        ))
        if existing:
            return _response(existing)
        raise HTTPException(status_code=503, detail="Could not save this fare right now.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Could not save this fare right now.") from exc
    return _response(row)


def _safe_link(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None
    except ValueError:
        return False


def _sanitize_snapshot_links(value):
    if isinstance(value, list):
        return [_sanitize_snapshot_links(item) for item in value]
    if isinstance(value, dict):
        return {key: (item if isinstance(item, str) and len(item) <= 1000 and _safe_link(item) else None)
                if key in {"bookingUrl", "affiliateUrl", "deepLink", "providerDeepLink", "outboundBookingUrl", "returnBookingUrl"}
                else _sanitize_snapshot_links(item) for key, item in value.items()}
    return value


@router.delete("/{fare_id}")
def delete_saved_fare(
    fare_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> dict:
    check_rate_limit(RateLimitCategory.CHEAP, request, user.id)
    row = db.get(SavedFareDB, fare_id) if len(fare_id) <= 36 else None
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved fare not found.")
    db.delete(row)
    db.commit()
    return {"deleted": True}
