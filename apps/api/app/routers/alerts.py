from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.alerts.schemas import AlertPreviewResponse, AlertRunResponse, CreateSavedSearchRequest, SavedSearchResponse
from app.alerts.service import (
    AlertPermissionError,
    AlertValidationError,
    SavedSearchNotFoundError,
    SavedSearchService,
)
from app.auth.dependencies import get_current_user_optional
from app.billing.usage import assert_saved_search_allowed
from app.config import settings
from app.database import get_db
from app.db.models import UserDB
from app.providers.errors import ProviderApiError, ProviderAuthError, ProviderConfigError
from app.services.flight_search_service import FlightProviderNotImplementedError, UnknownFlightProviderError
from app.security import RateLimitCategory, check_rate_limit
from app.tools.registry import ToolValidationError

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=SavedSearchResponse)
def create_alert(
    request: CreateSavedSearchRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB | None = Depends(get_current_user_optional),
) -> SavedSearchResponse:
    check_rate_limit(RateLimitCategory.ALERTS, http_request, user.id if user else None)
    try:
        if user:
            assert_saved_search_allowed(db, user, request.frequency)
        return SavedSearchService(db).create_saved_search(request, user=user)
    except AlertValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc


@router.get("/{saved_search_id}", response_model=SavedSearchResponse)
def get_alert(
    saved_search_id: str,
    http_request: Request,
    token: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> SavedSearchResponse:
    check_rate_limit(RateLimitCategory.ALERTS, http_request)
    return _handle_alert_errors(lambda: SavedSearchService(db).get_saved_search(saved_search_id, token))


@router.delete("/{saved_search_id}")
def delete_alert(
    saved_search_id: str,
    http_request: Request,
    token: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    check_rate_limit(RateLimitCategory.ALERTS, http_request)

    def run() -> dict[str, bool]:
        SavedSearchService(db).deactivate_saved_search(saved_search_id, token)
        return {"ok": True}

    return _handle_alert_errors(run)


@router.post("/{saved_search_id}/preview", response_model=AlertPreviewResponse)
def preview_alert(
    saved_search_id: str,
    http_request: Request,
    token: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> AlertPreviewResponse:
    check_rate_limit(RateLimitCategory.SEARCH, http_request)
    return _handle_alert_errors(lambda: SavedSearchService(db).preview_saved_search(saved_search_id, token))


@router.post("/{saved_search_id}/run", response_model=AlertRunResponse)
def run_alert(
    saved_search_id: str,
    http_request: Request,
    token: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> AlertRunResponse:
    check_rate_limit(RateLimitCategory.SEARCH, http_request)
    return _handle_alert_errors(lambda: SavedSearchService(db).run_one_alert(saved_search_id, token))


@router.post("/verify", response_model=SavedSearchResponse)
def verify_alert(
    http_request: Request,
    token: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> SavedSearchResponse:
    """Confirm an emailed watch. Limited because the token is a bearer secret."""
    check_rate_limit(RateLimitCategory.ALERTS, http_request)
    return _handle_alert_errors(lambda: SavedSearchService(db).verify_saved_search(token))


@router.post("/{saved_search_id}/resend-verification")
def resend_alert_verification(
    saved_search_id: str,
    http_request: Request,
    token: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Send a fresh confirmation link, invalidating the previous one.

    Rate limited hard: this endpoint causes mail to be sent to an address that
    has not yet agreed to receive any, which is precisely the capability an
    abuser wants.
    """
    check_rate_limit(RateLimitCategory.ALERTS, http_request)

    def run() -> dict[str, bool]:
        SavedSearchService(db).resend_verification(saved_search_id, token)
        # Always the same answer, whether or not it was already verified.
        return {"ok": True}

    return _handle_alert_errors(run)


@router.post("/run-due", response_model=list[AlertRunResponse])
def run_due_alerts(db: Session = Depends(get_db)) -> list[AlertRunResponse]:
    if not settings.enable_dev_tool_endpoints:
        raise HTTPException(status_code=404, detail="Alert runner endpoint is disabled.")
    return _handle_alert_errors(lambda: SavedSearchService(db).run_due_alerts())


def _handle_alert_errors(callback):
    try:
        return callback()
    except SavedSearchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlertPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AlertValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ToolValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FlightProviderNotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except UnknownFlightProviderError as exc:
        raise HTTPException(status_code=500, detail="Flight provider is not configured correctly.") from exc
    except ProviderConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (ProviderAuthError, ProviderApiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
