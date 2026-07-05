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
from app.billing.usage import AI_SEARCH, assert_ai_search_allowed, assert_origin_airports_allowed, increment_usage
from app.config import settings
from app.database import get_db
from app.db.models import UserDB
from app.rate_limit import rate_limit
from app.providers.errors import ProviderApiError, ProviderAuthError, ProviderConfigError
from app.services.flight_search_service import FlightProviderNotImplementedError, UnknownFlightProviderError
from app.tools.base import ToolContext
from app.tools.registry import build_default_tool_registry
from app.tools.schemas import ParsedTripIntent

router = APIRouter(prefix="/ai", tags=["ai"])
tool_registry = build_default_tool_registry()


@router.post("/parse-trip-intent", response_model=ParsedTripIntent)
def parse_trip_intent_route(request: ParseTripIntentRequest) -> ParsedTripIntent:
    return parse_trip_intent(request.message)


@router.post("/parse", response_model=AIParseOnlyResponse)
def parse_ai_request(request: AIParseOnlyRequest, db: Session = Depends(get_db)) -> AIParseOnlyResponse:
    return run_ai_parse(AISearchRequest(message=request.message), tool_registry, ToolContext(db=db))


@router.post("/search", response_model=AISearchResponse)
def ai_search(
    request: AISearchRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> AISearchResponse:
    rate_limit(
        "ai_search",
        settings.ai_search_rate_limit_max_attempts,
        settings.api_rate_limit_window_seconds,
    )(http_request)
    if request.originAirports:
        assert_origin_airports_allowed(user, len(request.originAirports))
    assert_ai_search_allowed(db, user)
    if user:
        increment_usage(db, user.id, AI_SEARCH)
    try:
        response = run_ai_search(request, tool_registry, ToolContext(db=db, user_id=user.id if user else None))
        if response.parsedRequest:
            assert_origin_airports_allowed(user, len(response.parsedRequest.originAirports))
        return response
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


@router.post("/search-preview", response_model=SearchPreviewResponse)
def search_preview(request: SearchPreviewRequest, db: Session = Depends(get_db)) -> SearchPreviewResponse:
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
