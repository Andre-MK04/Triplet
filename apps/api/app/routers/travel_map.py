from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth.dependencies import get_current_user_required
from app.database import get_db
from app.db.models import UserDB
from app.travel_map.schemas import (
    BulkCountryUpdate,
    CountryStateUpdate,
    TravelMapCountryResponse,
    TravelMapResponse,
    VisitResponse,
    VisitWriteRequest,
)
from app.travel_map.service import (
    TravelMapConflictError,
    TravelMapNotFoundError,
    TravelMapService,
    TravelMapValidationError,
)

router = APIRouter(prefix="/me/travel-map", tags=["travel-map"])


@router.get("", response_model=TravelMapResponse)
def get_travel_map(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> TravelMapResponse:
    return TravelMapService(db, user).get_map()


@router.patch("/countries/{country_code}", response_model=TravelMapCountryResponse)
def update_country_state(
    country_code: str,
    body: CountryStateUpdate,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> TravelMapCountryResponse:
    result = _run(db, lambda: TravelMapService(db, user).update_country(country_code, body))
    record_audit_event(
        db,
        "travel_map.country_updated",
        user_id=user.id,
        request=http_request,
        commit=True,
        country_code=country_code.upper(),
    )
    return result


@router.post("/countries/bulk", response_model=TravelMapResponse)
def bulk_update_countries(
    body: BulkCountryUpdate,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> TravelMapResponse:
    result = _run(db, lambda: TravelMapService(db, user).bulk_update(body))
    record_audit_event(
        db,
        "travel_map.countries_bulk_updated",
        user_id=user.id,
        request=http_request,
        commit=True,
        status=body.status,
        country_count=len(set(body.countryCodes)),
    )
    return result


@router.post("/countries/{country_code}/visits", response_model=VisitResponse, status_code=201)
def add_country_visit(
    country_code: str,
    body: VisitWriteRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> VisitResponse:
    result = _run(db, lambda: TravelMapService(db, user).add_visit(country_code, body))
    record_audit_event(
        db,
        "travel_map.visit_created",
        user_id=user.id,
        request=http_request,
        commit=True,
        country_code=country_code.upper(),
        visit_kind=body.kind,
    )
    return result


@router.patch("/visits/{visit_id}", response_model=VisitResponse)
def update_country_visit(
    visit_id: str,
    body: VisitWriteRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> VisitResponse:
    result = _run(db, lambda: TravelMapService(db, user).update_visit(visit_id, body))
    record_audit_event(
        db,
        "travel_map.visit_updated",
        user_id=user.id,
        request=http_request,
        commit=True,
        visit_id=visit_id,
    )
    return result


@router.delete("/visits/{visit_id}")
def delete_country_visit(
    visit_id: str,
    http_request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> dict[str, bool]:
    _run(db, lambda: TravelMapService(db, user).delete_visit(visit_id))
    record_audit_event(
        db,
        "travel_map.visit_deleted",
        user_id=user.id,
        request=http_request,
        commit=True,
        visit_id=visit_id,
    )
    return {"ok": True}


def _run(db: Session, operation: Callable):
    try:
        return operation()
    except TravelMapValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TravelMapConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TravelMapNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Travel map storage is temporarily unavailable.") from exc
