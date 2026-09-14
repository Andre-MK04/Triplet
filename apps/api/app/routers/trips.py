import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_optional, get_current_user_required
from app.billing.usage import (
    assert_ai_search_allowed,
    assert_origin_airports_allowed,
    record_ai_search,
)
from app.database import get_db
from app.db.models import UserDB
from app.db.repositories.trip_suggestions_repository import TripSuggestionsRepository
from app.models import (
    AdvancedTripSearchRequest,
    AdvancedTripSearchResponse,
    TripSearchRequest,
    TripSearchResponse,
)
from app.preferences.resolution import resolve_search_preferences
from app.config import settings
from app.observability import events
from app.security import RateLimitCategory, check_rate_limit, consume_ai_call
from app.providers.errors import ProviderApiError, ProviderAuthError, ProviderConfigError
from app.services.flight_search_service import (
    FlightProviderNotImplementedError,
    UnknownFlightProviderError,
)
from app.tools.base import ToolContext
from app.tools.registry import build_default_tool_registry
from app.tools.travel_tools import UnsupportedFlightPlaceError

router = APIRouter(prefix="/trips", tags=["trips"])
tool_registry = build_default_tool_registry()


@router.post("/search", response_model=TripSearchResponse)
def search_trips(
    request: TripSearchRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> TripSearchResponse:
    check_rate_limit(RateLimitCategory.SEARCH, http_request, user.id if user else None)
    if request.endDate < request.startDate:
        raise HTTPException(status_code=400, detail="endDate must be on or after startDate")
    if request.maxTripLengthDays < request.minTripLengthDays:
        raise HTTPException(status_code=400, detail="maxTripLengthDays must be greater than or equal to minTripLengthDays")
    assert_origin_airports_allowed(user, len(request.originAirports))

    context = ToolContext(db=db, user_id=user.id if user else None)
    started = time.perf_counter()
    try:
        result = tool_registry.run_tool("search_trips", request, context)
        events.search_completed(
            trip_count=len(result.trips),
            duration_ms=round((time.perf_counter() - started) * 1000),
            provider=result.providerUsed,
            cached=result.cachedResultsUsed,
            stale_fares=sum(
                1 for trip in result.trips if (trip.price and trip.price.freshness == "stale")
            ),
            origins=len(request.originAirports),
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Database is not ready. Start the {settings.app_name} PostgreSQL container, "
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
    except UnsupportedFlightPlaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TripSearchResponse.model_validate(result.model_dump())


@router.post("/advanced-search", response_model=AdvancedTripSearchResponse)
def advanced_search(
    request: AdvancedTripSearchRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> AdvancedTripSearchResponse:
    """Run a structured search with server-owned profile resolution.

    This route does not call a language model or consume AI usage. Explicit
    request values win; profile values only fill omissions.
    """
    from app.db.models import UserTravelProfileDB

    if (request.startDate is None) != (request.endDate is None):
        raise HTTPException(status_code=400, detail="Choose both a start and end date, or leave both to your profile.")

    profile_row = db.get(UserTravelProfileDB, user.id)
    if not profile_row:
        raise HTTPException(status_code=400, detail="Complete your travel profile before using advanced search.")

    comfort_modes = dict(profile_row.comfort_rule_modes or {})
    explicit = request.model_dump(exclude_none=True)
    if request.comfortRules:
        explicit["directOnly"] = request.comfortRules.get("direct_only") == "require"
        explicit["includeBaggage"] = request.comfortRules.get("cabin_bag_included") in {"prefer", "require"}
    profile = {
        "originAirports": list(profile_row.origin_airports or []),
        "preferredTripLengthMin": profile_row.preferred_trip_length_min,
        "preferredTripLengthMax": profile_row.preferred_trip_length_max,
        "preferredTravelStyles": list(profile_row.preferred_trip_types or []),
        "absoluteMaxBudget": profile_row.absolute_max_budget,
        "dealSensitivity": profile_row.deal_sensitivity,
        "comfortRules": comfort_modes,
        "spontaneityLevel": profile_row.spontaneity,
        "directOnly": comfort_modes.get("direct_only") == "require",
        "includeBaggage": comfort_modes.get("cabin_bag_included") in {"prefer", "require"},
    }
    resolved = resolve_search_preferences(explicit, profile)
    origins = [code.upper() for code in resolved.values["originAirports"]]
    if not origins:
        raise HTTPException(status_code=400, detail="Add at least one origin airport to your travel profile.")

    trip_plan = request.tripPlan or resolved.values["tripPlan"]
    if trip_plan == "multi_city" and not request.routeStops:
        raise HTTPException(status_code=400, detail="Multi-city search needs at least two destinations in travel order.")

    # No hard budget means broad discovery, not an invisible profile cap. The
    # engine still requires a numeric ceiling, so 5000 is an internal safety
    # bound; hardBudgetApplied tells clients not to present it as the user's cap.
    hard_budget = resolved.values["maxBudget"] is not None
    engine_budget = float(resolved.values["maxBudget"] or 5000)
    search_request = TripSearchRequest(
        originAirports=origins,
        destinationAirports=(
            [code.upper() for code in request.destinationAirports]
            if request.destinationAirports else None
        ),
        destinationCountries=[code.upper() for code in (request.destinationCountries or [])],
        destinationRegions=list(request.destinationRegions or []),
        destinationContinents=list(request.destinationContinents or []),
        returnOriginAirports=(
            [code.upper() for code in request.returnOriginAirports]
            if request.returnOriginAirports else None
        ),
        startDate=resolved.values["startDate"],
        endDate=resolved.values["endDate"],
        minTripLengthDays=resolved.values["minTripLengthDays"],
        maxTripLengthDays=resolved.values["maxTripLengthDays"],
        maxBudget=engine_budget,
        maxGroundTransferHours=resolved.values["maxGroundTransferHours"],
        tripStyle=resolved.values["tripStyle"],
        tripPlan=trip_plan,
        routeStops=[code.upper() for code in request.routeStops] if request.routeStops else None,
        directOnly=bool(resolved.values["directOnly"]),
        includeBaggage=bool(resolved.values["includeBaggage"]),
        travelStyles=list(resolved.values["travelStyles"]),
    )

    result = search_trips(search_request, http_request, db, user)
    source_map = dict(resolved.sourceMap)
    for field_name in (
        "destinationAirports",
        "destinationCountries",
        "destinationRegions",
        "destinationContinents",
        "returnOriginAirports",
        "routeStops",
    ):
        source_map[field_name] = "search" if getattr(request, field_name) else "default"

    count = len(result.trips)
    message = (
        f"Found {count} observed trip {'option' if count == 1 else 'options'} from your structured search."
        if count
        else "No observed fares matched those structured filters right now."
    )
    return AdvancedTripSearchResponse(
        **result.model_dump(),
        message=message,
        parsedRequest=search_request,
        sourceMap=source_map,
        hardBudgetApplied=hard_budget,
    )


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
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> dict:
    """Generate (once, then cache) a personalised day-by-day plan for this deal."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.ai.providers import AIProviderError
    from app.db.models import UserTravelProfileDB
    from app.itinerary.service import ItineraryUnavailable, generate_itinerary

    check_rate_limit(RateLimitCategory.AI, http_request, user.id if user else None)
    row = TripSuggestionsRepository(db).get_visible(suggestion_id, user_id=user.id if user else None)
    if not row:
        raise HTTPException(status_code=404, detail="Trip suggestion not found or expired.")
    if row.itinerary:
        return {"itinerary": row.itinerary, "cached": True}

    # A new itinerary is a billable model call. It belongs under the same
    # per-account quota and service-wide circuit breaker as AI search; cached
    # plans remain free to reopen.
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=503,
            detail="AI itineraries are not enabled in this environment.",
        )
    assert_ai_search_allowed(db, user)
    if not consume_ai_call():
        raise HTTPException(
            status_code=503,
            detail="AI itinerary generation is paused for today. Please try again tomorrow.",
        )
    if user:
        record_ai_search(db, user)

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
