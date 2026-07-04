from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_optional
from app.billing.usage import assert_origin_airports_allowed
from app.database import get_db
from app.db.models import UserDB
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

    context = ToolContext(db=db)
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
