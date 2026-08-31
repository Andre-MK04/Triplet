from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.intent_parser import parse_trip_intent
from app.ai.orchestrator import build_search_preview, run_ai_parse, run_ai_search
from app.ai.schemas import (
    AIParseOnlyRequest,
    AIParseOnlyResponse,
    AISearchRequest,
    AISearchResponse,
    ParseTripIntentRequest,
    SearchPreviewRequest,
    SearchPreviewResponse,
)
from app.auth.dependencies import get_current_user_optional
from app.billing.entitlements import get_entitlements
from app.billing.usage import assert_ai_search_allowed, assert_origin_airports_allowed, record_ai_search
from app.config import settings
from app.database import get_db
from app.db.models import UserDB
from app.security import RateLimitCategory, check_rate_limit
from app.providers.errors import ProviderApiError, ProviderAuthError, ProviderConfigError
from app.services.flight_search_service import FlightProviderNotImplementedError, UnknownFlightProviderError
from app.tools.base import ToolContext
from app.tools.registry import build_default_tool_registry
from app.tools.travel_tools import UnsupportedFlightPlaceError
from app.tools.schemas import ParsedTripIntent

router = APIRouter(prefix="/ai", tags=["ai"])
tool_registry = build_default_tool_registry()


@router.post("/parse-trip-intent", response_model=ParsedTripIntent)
def parse_trip_intent_route(
    request: ParseTripIntentRequest,
    http_request: Request,
    user: UserDB | None = Depends(get_current_user_optional),
) -> ParsedTripIntent:
    """Rule-based parsing only — no model is called, so this is a cheap route."""
    check_rate_limit(RateLimitCategory.CHEAP, http_request, user.id if user else None)
    return parse_trip_intent(request.message)


@router.post("/parse", response_model=AIParseOnlyResponse)
def parse_ai_request(
    request: AIParseOnlyRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> AIParseOnlyResponse:
    """Parse a request with the model.

    This reaches a language model, so it carries the same limit and quota as
    /ai/search. It had neither before, which made it a free unlimited way to
    spend model credit while the endpoint it shadowed was protected.
    """
    check_rate_limit(RateLimitCategory.AI, http_request, user.id if user else None)
    assert_ai_search_allowed(db, user)
    if user:
        record_ai_search(db, user)
    return run_ai_parse(AISearchRequest(message=request.message), tool_registry, ToolContext(db=db))


@router.post("/search", response_model=AISearchResponse)
def ai_search(
    request: AISearchRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> AISearchResponse:
    check_rate_limit(RateLimitCategory.AI, http_request, user.id if user else None)
    if request.originAirports:
        assert_origin_airports_allowed(user, len(request.originAirports))
    assert_ai_search_allowed(db, user)
    if user:
        record_ai_search(db, user)
    try:
        # Engine-chosen origins are clamped to the plan limit inside the search
        # (see ToolContext.max_origin_airports) rather than rejected after the fact.
        context = ToolContext(
            db=db,
            user_id=user.id if user else None,
            max_origin_airports=get_entitlements(user)["maxOriginAirports"],
        )
        return run_ai_search(request, tool_registry, context)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc
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


@router.post("/search-preview", response_model=SearchPreviewResponse)
def search_preview(
    request: SearchPreviewRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> SearchPreviewResponse:
    """Parse a request and run the search it describes.

    Parsing is rule-based here, but the search behind it reaches paid flight
    providers, so it is limited as a search. It was previously unlimited, which
    made it the cheapest way to spend Triplet's provider budget.
    """
    check_rate_limit(RateLimitCategory.SEARCH, http_request, user.id if user else None)
    try:
        return build_search_preview(request.message, tool_registry, ToolContext(db=db))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc
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
