from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.alerts.schemas import AlertPreviewResponse, AlertRunResponse, CreateSavedSearchRequest, SavedSearchResponse, UpdateSavedSearchRequest
from app.alerts.service import (
    AlertValidationError,
    SavedSearchNotFoundError,
    SavedSearchService,
)
from app.auth.dependencies import get_current_user_required
from app.auth.service import auth_user_response
from app.billing.service import billing_status
from app.billing.usage import assert_saved_search_allowed
from app.database import get_db
from app.db.models import UserDB
from app.providers.errors import ProviderApiError, ProviderAuthError, ProviderConfigError
from app.services.flight_search_service import FlightProviderNotImplementedError, UnknownFlightProviderError
from app.tools.registry import ToolValidationError

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
def list_saved_searches(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> list[SavedSearchResponse]:
    return SavedSearchService(db).list_user_saved_searches(user)


@router.get("/usage")
def get_usage(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> dict:
    status = billing_status(db, user)
    return {"usage": status["usage"], "limits": status["limits"], "plan": status["plan"]}


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> dict:
    searches = SavedSearchService(db).list_user_saved_searches(user)
    status = billing_status(db, user)
    return {
        "user": auth_user_response(user),
        "billing": status,
        "usage": status["usage"],
        "savedSearches": searches,
        "savedSearchSummary": {
            "total": len(searches),
            "active": len([search for search in searches if search.isActive]),
        },
    }


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


@router.patch("/saved-searches/{saved_search_id}", response_model=SavedSearchResponse)
def update_saved_search(
    saved_search_id: str,
    request: UpdateSavedSearchRequest,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> SavedSearchResponse:
    def run() -> SavedSearchResponse:
        if request.frequency:
            assert_saved_search_allowed(db, user, request.frequency)
        return SavedSearchService(db).update_user_saved_search(user, saved_search_id, request)

    return _handle_saved_search_errors(run)


@router.post("/saved-searches/{saved_search_id}/pause", response_model=SavedSearchResponse)
def pause_saved_search(
    saved_search_id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> SavedSearchResponse:
    def run() -> SavedSearchResponse:
        return SavedSearchService(db).deactivate_user_saved_search(user, saved_search_id)

    return _handle_saved_search_errors(run)


@router.post("/saved-searches/{saved_search_id}/resume", response_model=SavedSearchResponse)
def resume_saved_search(
    saved_search_id: str,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> SavedSearchResponse:
    def run() -> SavedSearchResponse:
        service = SavedSearchService(db)
        current = service.get_user_saved_search(user, saved_search_id)
        assert_saved_search_allowed(db, user, current.frequency)
        return service.resume_user_saved_search(user, saved_search_id)

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
    except ProviderConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (ProviderAuthError, ProviderApiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
