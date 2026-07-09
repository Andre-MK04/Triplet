from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_optional
from app.billing.usage import assert_origin_airports_allowed
from app.database import get_db
from app.db.models import UserDB
from app.db.repositories.trip_suggestions_repository import TripSuggestionsRepository
from app.models import TripSearchRequest, TripSearchResponse
from app.config import settings
from app.rate_limit import rate_limit
from app.providers.errors import ProviderApiError, ProviderAuthError, ProviderConfigError
from app.services.flight_search_service import (
    FlightProviderNotImplementedError,
    UnknownFlightProviderError,
)
from app.tools.base import ToolContext
from app.tools.registry import build_default_tool_registry

router = APIRouter(prefix="/trips", tags=["trips"])
tool_registry = build_default_tool_registry()


@router.post("/search", response_model=TripSearchResponse)
def search_trips(
    request: TripSearchRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> TripSearchResponse:
    rate_limit(
        "trips_search",
        settings.trips_search_rate_limit_max_attempts,
        settings.api_rate_limit_window_seconds,
    )(http_request)
    if request.endDate < request.startDate:
        raise HTTPException(status_code=400, detail="endDate must be on or after startDate")
    if request.maxTripLengthDays < request.minTripLengthDays:
        raise HTTPException(status_code=400, detail="maxTripLengthDays must be greater than or equal to minTripLengthDays")
    assert_origin_airports_allowed(user, len(request.originAirports))

    context = ToolContext(db=db, user_id=user.id if user else None)
    try:
        result = tool_registry.run_tool("search_trips", request, context)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is not ready. Start the Triplet PostgreSQL container, "
                "run migrations, and seed the database."
            ),
        ) from exc
    except FlightProviderNotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except UnknownFlightProviderError as exc:
        raise HTTPException(status_code=500, detail="Flight provider is not configured correctly.") from exc
    except ProviderConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (ProviderAuthError, ProviderApiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TripSearchResponse.model_validate(result.model_dump())


@router.get("/suggestions/{suggestion_id}")
def get_trip_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> dict:
    row = TripSuggestionsRepository(db).get_visible(suggestion_id, user_id=user.id if user else None)
    if not row:
        raise HTTPException(status_code=404, detail="Trip suggestion not found or expired.")
    return {
        "id": row.id,
        "title": row.title,
        "tripType": row.trip_type,
        "createdAt": row.created_at,
        "expiresAt": row.expires_at,
        "dealScore": row.deal_score,
        "fitScore": row.fit_score,
        "trip": row.payload,
        "itinerary": row.itinerary,
        "disclaimer": "Prices were observed when this suggestion was created and may have changed.",
    }


@router.post("/suggestions/{suggestion_id}/plan")
def plan_trip_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> dict:
    """Generate (once, then cache) a personalised day-by-day plan for this deal."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.ai.providers import AIProviderError
    from app.db.models import UserTravelProfileDB
    from app.itinerary.service import ItineraryUnavailable, generate_itinerary

    row = TripSuggestionsRepository(db).get_visible(suggestion_id, user_id=user.id if user else None)
    if not row:
        raise HTTPException(status_code=404, detail="Trip suggestion not found or expired.")
    if row.itinerary:
        return {"itinerary": row.itinerary, "cached": True}

    profile = None
    if user:
        profile_row = db.get(UserTravelProfileDB, user.id)
        if profile_row:
            profile = {
                "preferredTripTypes": profile_row.preferred_trip_types,
                "comfortRules": profile_row.comfort_rules,
                "budgetComfortZone": profile_row.budget_comfort_zone,
            }
    try:
        plan = generate_itinerary(row.payload, profile, ai_enabled=settings.ai_enabled)
    except ItineraryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderError as exc:
        # Covers missing key (AIProviderConfigError) and upstream/model failures.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    row.itinerary = plan.model_dump()
    flag_modified(row, "itinerary")
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    return {"itinerary": plan.model_dump(), "cached": False}
