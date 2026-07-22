from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.alerts.schemas import AlertPreviewResponse, AlertRunResponse, CreateSavedSearchRequest, SavedSearchResponse, UpdateSavedSearchRequest
from app.alerts.service import (
    AlertValidationError,
    SavedSearchNotFoundError,
    SavedSearchService,
)
from app.auth.dependencies import get_current_user_required
from app.auth.service import auth_user_response
from app.billing.service import billing_status
from app.billing.usage import assert_origin_airports_allowed, assert_saved_search_allowed
from app.database import get_db
from app.db.models import UserDB, UserTravelProfileDB
from app.models.travel_profile import (
    TravelProfileResponse,
    TravelProfileUpdateRequest,
    default_profile_response,
)
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


@router.get("/export")
def export_my_data(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> dict:
    """GDPR right of access: everything we hold linked to this account, as JSON."""
    from app.privacy.service import export_user_data

    return export_user_data(db, user)


@router.get("/travel-profile", response_model=TravelProfileResponse)
def get_travel_profile(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> TravelProfileResponse:
    row = db.get(UserTravelProfileDB, user.id)
    if not row:
        return default_profile_response(user.id)
    return _profile_to_response(row)


@router.put("/travel-profile", response_model=TravelProfileResponse)
def upsert_travel_profile(
    request: TravelProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> TravelProfileResponse:
    assert_origin_airports_allowed(user, len(request.originAirports))
    row = db.get(UserTravelProfileDB, user.id)
    if not row:
        row = UserTravelProfileDB(user_id=user.id)
        db.add(row)
    row.home_location = request.homeLocation
    row.origin_airports = request.originAirports
    row.max_airport_travel_time_minutes = request.maxAirportTravelTimeMinutes
    row.preferred_trip_types = list(request.preferredTripTypes)
    row.preferred_trip_length_min = request.preferredTripLengthMin
    row.preferred_trip_length_max = request.preferredTripLengthMax
    row.budget_comfort_zone = request.budgetComfortZone
    row.spontaneity = request.spontaneity
    row.comfort_rules = list(request.comfortRules)
    row.open_jaw_willingness = request.openJawWillingness
    row.notification_frequency = request.notificationFrequency
    row.excluded_airlines = request.excludedAirlines
    row.preferred_months = request.preferredMonths
    # Profile v2 fields.
    row.base_location_id = request.baseLocationId
    row.base_latitude = request.baseLatitude
    row.base_longitude = request.baseLongitude
    row.max_airport_distance_km = request.maxAirportDistanceKm
    row.recommended_origin_airports = list(request.recommendedOriginAirports)
    row.deal_sensitivity = request.dealSensitivity
    row.absolute_max_budget = request.absoluteMaxBudget
    row.alert_trigger_mode = request.alertTriggerMode
    row.comfort_rule_modes = dict(request.comfortRuleModes)
    row.theme_preference = request.themePreference
    if row.onboarding_completed_at is None:
        from datetime import datetime as _dt

        row.onboarding_completed_at = _dt.utcnow()
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc
    db.refresh(row)
    record_audit_event(db, "profile.travel_profile_updated", user_id=user.id, commit=True)
    return _profile_to_response(row)


def _profile_to_response(row: UserTravelProfileDB) -> TravelProfileResponse:
    return TravelProfileResponse(
        userId=row.user_id,
        isComplete=True,
        homeLocation=row.home_location,
        originAirports=row.origin_airports,
        maxAirportTravelTimeMinutes=row.max_airport_travel_time_minutes,
        preferredTripTypes=row.preferred_trip_types,
        preferredTripLengthMin=row.preferred_trip_length_min,
        preferredTripLengthMax=row.preferred_trip_length_max,
        budgetComfortZone=row.budget_comfort_zone,
        spontaneity=row.spontaneity,
        comfortRules=row.comfort_rules,
        openJawWillingness=row.open_jaw_willingness,
        notificationFrequency=row.notification_frequency,
        excludedAirlines=row.excluded_airlines,
        preferredMonths=row.preferred_months,
        baseLocationId=row.base_location_id,
        baseLatitude=row.base_latitude,
        baseLongitude=row.base_longitude,
        maxAirportDistanceKm=row.max_airport_distance_km,
        recommendedOriginAirports=row.recommended_origin_airports or [],
        dealSensitivity=row.deal_sensitivity or "balanced",
        absoluteMaxBudget=row.absolute_max_budget,
        alertTriggerMode=row.alert_trigger_mode or "any",
        comfortRuleModes=row.comfort_rule_modes or {},
        themePreference=row.theme_preference,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


@router.post("/saved-searches", response_model=SavedSearchResponse)
def create_saved_search(
    request: CreateSavedSearchRequest,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> SavedSearchResponse:
    try:
        assert_saved_search_allowed(db, user, request.frequency)
        created = SavedSearchService(db).create_user_saved_search(user, request)
        record_audit_event(db, "watch.created", user_id=user.id, commit=True, watch_id=created.id)
        return created
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
        record_audit_event(db, "watch.deleted", user_id=user.id, commit=True, watch_id=saved_search_id)
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
        updated = SavedSearchService(db).update_user_saved_search(user, saved_search_id, request)
        record_audit_event(db, "watch.updated", user_id=user.id, commit=True, watch_id=saved_search_id)
        return updated

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
