from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.alerts.schemas import AlertPreviewResponse, AlertRunResponse, CreateSavedSearchRequest, SavedSearchResponse
from app.alerts.service import (
    AlertValidationError,
    SavedSearchNotFoundError,
    SavedSearchService,
)
from app.auth.dependencies import get_current_user_required
from app.billing.usage import assert_saved_search_allowed
from app.database import get_db
from app.db.models import UserDB
from app.providers.amadeus import AmadeusApiError, AmadeusAuthError, AmadeusConfigError
from app.services.flight_search_service import FlightProviderNotImplementedError, UnknownFlightProviderError
from app.tools.registry import ToolValidationError

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
def list_saved_searches(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> list[SavedSearchResponse]:
    return SavedSearchService(db).list_user_saved_searches(user)


@router.post("/saved-searches", response_model=SavedSearchResponse)
def create_saved_search(
    request: CreateSavedSearchRequest,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> SavedSearchResponse:
    try:
        assert_saved_search_allowed(db, user, request.frequency)
        return SavedSearchService(db).create_user_saved_search(user, request)
    except AlertValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc


@router.delete("/saved-searches/{saved_search_id}")
def delete_saved_search(
    saved_search_id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> dict[str, bool]:
    def run() -> dict[str, bool]:
        SavedSearchService(db).deactivate_user_saved_search(user, saved_search_id)
        return {"ok": True}

    return _handle_saved_search_errors(run)


@router.post("/saved-searches/{saved_search_id}/preview", response_model=AlertPreviewResponse)
def preview_saved_search(
    saved_search_id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> AlertPreviewResponse:
    return _handle_saved_search_errors(lambda: SavedSearchService(db).preview_user_saved_search(user, saved_search_id))


@router.post("/saved-searches/{saved_search_id}/run", response_model=AlertRunResponse)
def run_saved_search(
    saved_search_id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> AlertRunResponse:
    return _handle_saved_search_errors(lambda: SavedSearchService(db).run_user_alert(user, saved_search_id))


def _handle_saved_search_errors(callback):
    try:
        return callback()
    except SavedSearchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlertValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ToolValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FlightProviderNotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except UnknownFlightProviderError as exc:
        raise HTTPException(status_code=500, detail="Flight provider is not configured correctly.") from exc
    except AmadeusConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (AmadeusAuthError, AmadeusApiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
