import smtplib
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.email import EmailProviderError, build_email_provider
from app.alerts.schemas import AlertPreviewResponse, AlertRunResponse, CreateSavedSearchRequest, SavedSearchResponse
from app.alerts.token_utils import generate_token, hash_token, verify_token
from app.config import settings
from app.db.models import AlertDeliveryDB, AlertRunDB, SavedSearchDB, UserDB
from app.db.repositories.airports_repository import AirportsRepository
from app.models import TripSearchRequest
from app.tools.base import ToolContext
from app.tools.registry import build_default_tool_registry
from app.tools.schemas import SearchTripsOutput


class AlertPermissionError(PermissionError):
    pass


class SavedSearchNotFoundError(KeyError):
    pass


class AlertValidationError(ValueError):
    pass


class SavedSearchService:
    def __init__(self, db: Session):
        self.db = db
        self.registry = build_default_tool_registry()

    def create_saved_search(self, request: CreateSavedSearchRequest, user: UserDB | None = None) -> SavedSearchResponse:
        self._validate_request(request)
        manage_token = generate_token()
        unsubscribe_token = generate_token()
        row = SavedSearchDB(
            id=str(uuid4()),
            user_id=user.id if user else None,
            email=request.email,
            name=request.name,
            origin_airports=request.originAirports,
            start_date=request.startDate,
            end_date=request.endDate,
            min_trip_length_days=request.minTripLengthDays,
            max_trip_length_days=request.maxTripLengthDays,
            max_budget=request.maxBudget,
            max_ground_transfer_hours=request.maxGroundTransferHours,
            trip_style=request.tripStyle,
            direct_only=request.directOnly,
            include_baggage=request.includeBaggage,
            frequency=request.frequency,
            is_active=True,
            manage_token_hash=hash_token(manage_token),
            unsubscribe_token_hash=hash_token(unsubscribe_token),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_response(row, manage_token=manage_token, unsubscribe_token=unsubscribe_token)

    def list_user_saved_searches(self, user: UserDB) -> list[SavedSearchResponse]:
        rows = self.db.scalars(
            select(SavedSearchDB)
            .where(SavedSearchDB.user_id == user.id)
            .order_by(SavedSearchDB.created_at.desc())
        ).all()
        return [self._to_response(row) for row in rows]

    def create_user_saved_search(self, user: UserDB, request: CreateSavedSearchRequest) -> SavedSearchResponse:
        if request.email != user.email:
            request = request.model_copy(update={"email": user.email})
        return self.create_saved_search(request, user=user)

    def deactivate_user_saved_search(self, user: UserDB, saved_search_id: str) -> None:
        row = self._get_user_saved_search(user, saved_search_id)
        row.is_active = False
        row.updated_at = datetime.utcnow()
        self.db.commit()

    def preview_user_saved_search(self, user: UserDB, saved_search_id: str) -> AlertPreviewResponse:
        row = self._get_user_saved_search(user, saved_search_id)
        output = self._search(row)
        return AlertPreviewResponse(
            savedSearch=self._to_response(row),
            matchingTrips=output.trips,
            providerMetadata=output.providerMetadata,
        )

    def run_user_alert(self, user: UserDB, saved_search_id: str) -> AlertRunResponse:
        row = self._get_user_saved_search(user, saved_search_id)
        return self.run_saved_search_alert(row)

    def get_saved_search(self, saved_search_id: str, token: str) -> SavedSearchResponse:
        row = self._get_authorized(saved_search_id, token, allow_unsubscribe=True)
        return self._to_response(row)

    def deactivate_saved_search(self, saved_search_id: str, token: str) -> None:
        row = self._get_authorized(saved_search_id, token, allow_unsubscribe=True)
        row.is_active = False
        row.updated_at = datetime.utcnow()
        self.db.commit()

    def preview_saved_search(self, saved_search_id: str, token: str) -> AlertPreviewResponse:
        row = self._get_authorized(saved_search_id, token)
        output = self._search(row)
        return AlertPreviewResponse(
            savedSearch=self._to_response(row),
            matchingTrips=output.trips,
            providerMetadata=output.providerMetadata,
        )

    def list_due_saved_searches(self, now: datetime | None = None) -> list[SavedSearchDB]:
        now = now or datetime.utcnow()
        rows = self.db.scalars(select(SavedSearchDB).where(SavedSearchDB.is_active.is_(True))).all()
        return [row for row in rows if self._is_due(row, now)]

    def run_due_alerts(self) -> list[AlertRunResponse]:
        return [self.run_saved_search_alert(row) for row in self.list_due_saved_searches()]

    def run_one_alert(self, saved_search_id: str, token: str) -> AlertRunResponse:
        row = self._get_authorized(saved_search_id, token)
        return self.run_saved_search_alert(row)

    def run_saved_search_alert(self, row: SavedSearchDB) -> AlertRunResponse:
        run = AlertRunDB(id=str(uuid4()), saved_search_id=row.id, status="running", result_count=0)
        self.db.add(run)
        self.db.flush()
        notification_sent = False
        warnings: list[str] = []
        try:
            output = self._search(row)
            trips = output.trips
            best_trip = min(trips, key=lambda trip: trip.totalPrice) if trips else None
            best_price = best_trip.totalPrice if best_trip else None
            should_notify = best_trip is not None and self._should_notify(row, best_price)
            row.last_checked_at = datetime.utcnow()
            if best_trip:
                row.last_best_price = best_price
                row.last_best_trip_id = best_trip.id

            if should_notify:
                self._send_delivery(row, run, output)
                row.last_notified_at = datetime.utcnow()
                notification_sent = True

            run.status = "success" if trips else "no_results"
            run.provider_used = output.providerUsed
            run.result_count = len(trips)
            run.best_price = best_price
            if output.providerWarnings:
                warnings.extend(output.providerWarnings)
        except Exception as exc:  # noqa: BLE001 - alert runs should log failures, not crash loops.
            run.status = "error"
            run.error_message = str(exc)
            warnings.append(str(exc))
        finally:
            run.finished_at = datetime.utcnow()
            row.updated_at = datetime.utcnow()
            self.db.commit()

        return AlertRunResponse(
            savedSearchId=row.id,
            status=run.status,
            resultCount=run.result_count,
            bestPrice=run.best_price,
            notificationSent=notification_sent,
            warnings=warnings,
        )

    def _send_delivery(self, row: SavedSearchDB, run: AlertRunDB, output: SearchTripsOutput) -> None:
        subject = f"{settings.app_name} alert: {len(output.trips)} matching trip(s)"
        manage_token_note = "Use your manage/unsubscribe links from the alert creation response."
        text_body = build_alert_text(row, output, manage_token_note)
        html_body = "<pre>" + text_body.replace("&", "&amp;").replace("<", "&lt;") + "</pre>"
        delivery = AlertDeliveryDB(
            id=str(uuid4()),
            saved_search_id=row.id,
            alert_run_id=run.id,
            email=row.email,
            subject=subject,
            status="sent",
            provider=settings.email_provider,
        )
        try:
            provider = build_email_provider()
            delivery.provider = provider.provider_name
            provider.send_email(row.email, subject, html_body, text_body)
        except (EmailProviderError, OSError, smtplib.SMTPException) as exc:
            delivery.status = "error"
            delivery.error_message = str(exc)
        self.db.add(delivery)

    def _search(self, row: SavedSearchDB) -> SearchTripsOutput:
        request = saved_search_to_trip_request(row)
        result = self.registry.run_tool("search_trips", request.model_dump(mode="json"), ToolContext(db=self.db))
        return SearchTripsOutput.model_validate(result)

    def _validate_request(self, request: CreateSavedSearchRequest) -> None:
        if request.endDate < request.startDate:
            raise AlertValidationError("endDate must be on or after startDate.")
        if (request.endDate - request.startDate).days > 180:
            raise AlertValidationError("Saved alert date range cannot exceed 180 days.")
        if request.maxTripLengthDays < request.minTripLengthDays:
            raise AlertValidationError("maxTripLengthDays must be greater than or equal to minTripLengthDays.")
        known = {airport.code for airport in AirportsRepository(self.db).list_airports()}
        invalid = [code for code in request.originAirports if code not in known]
        if invalid:
            raise AlertValidationError(f"Unknown origin airport code(s): {', '.join(invalid)}.")

    def _get_authorized(self, saved_search_id: str, token: str, allow_unsubscribe: bool = False) -> SavedSearchDB:
        row = self.db.get(SavedSearchDB, saved_search_id)
        if not row:
            raise SavedSearchNotFoundError("Saved search not found.")
        valid = verify_token(token, row.manage_token_hash)
        if allow_unsubscribe:
            valid = valid or verify_token(token, row.unsubscribe_token_hash)
        if not valid:
            raise AlertPermissionError("Invalid alert token.")
        return row

    def _get_user_saved_search(self, user: UserDB, saved_search_id: str) -> SavedSearchDB:
        row = self.db.get(SavedSearchDB, saved_search_id)
        if not row or row.user_id != user.id:
            raise SavedSearchNotFoundError("Saved search not found.")
        return row

    def _is_due(self, row: SavedSearchDB, now: datetime) -> bool:
        if row.last_checked_at is None:
            return True
        interval = timedelta(days=7 if row.frequency == "weekly" else 1)
        return row.last_checked_at <= now - interval

    def _should_notify(self, row: SavedSearchDB, best_price: float) -> bool:
        if row.last_notified_at:
            cooldown = timedelta(hours=settings.alerts_min_hours_between_notifications)
            if row.last_notified_at > datetime.utcnow() - cooldown:
                return False
        if row.last_notified_at is None:
            return True
        if row.last_best_price is None:
            return True
        return best_price <= row.last_best_price - 10

    def _to_response(
        self,
        row: SavedSearchDB,
        manage_token: str | None = None,
        unsubscribe_token: str | None = None,
    ) -> SavedSearchResponse:
        return saved_search_to_response(row, manage_token, unsubscribe_token)


def saved_search_to_trip_request(row: SavedSearchDB) -> TripSearchRequest:
    return TripSearchRequest(
        originAirports=row.origin_airports,
        startDate=row.start_date,
        endDate=row.end_date,
        minTripLengthDays=row.min_trip_length_days,
        maxTripLengthDays=row.max_trip_length_days,
        maxBudget=row.max_budget,
        maxGroundTransferHours=row.max_ground_transfer_hours,
        tripStyle=row.trip_style,
        directOnly=row.direct_only if row.direct_only is not None else False,
        includeBaggage=row.include_baggage if row.include_baggage is not None else False,
    )


def saved_search_to_response(
    row: SavedSearchDB,
    manage_token: str | None = None,
    unsubscribe_token: str | None = None,
) -> SavedSearchResponse:
    base_url = settings.alerts_public_base_url.rstrip("/")
    return SavedSearchResponse(
        id=row.id,
        email=row.email,
        name=row.name,
        originAirports=row.origin_airports,
        startDate=row.start_date,
        endDate=row.end_date,
        minTripLengthDays=row.min_trip_length_days,
        maxTripLengthDays=row.max_trip_length_days,
        maxBudget=row.max_budget,
        maxGroundTransferHours=row.max_ground_transfer_hours,
        tripStyle=row.trip_style,
        directOnly=row.direct_only,
        includeBaggage=row.include_baggage,
        frequency=row.frequency,
        isActive=row.is_active,
        createdAt=row.created_at,
        lastCheckedAt=row.last_checked_at,
        lastNotifiedAt=row.last_notified_at,
        manageUrl=f"{base_url}/alerts/{row.id}?token={manage_token}" if manage_token else None,
        unsubscribeUrl=f"{base_url}/alerts/{row.id}/unsubscribe?token={unsubscribe_token}" if unsubscribe_token else None,
    )


def build_alert_text(row: SavedSearchDB, output: SearchTripsOutput, token_note: str) -> str:
    lines = [
        f"{settings.app_name} alert: {row.name or 'Saved search'}",
        "Prices are not guaranteed and may change.",
        "",
    ]
    for trip in output.trips[: settings.alerts_max_results_per_email]:
        lines.append(
            f"- {trip.outboundFlight.origin}->{trip.outboundFlight.destination} / "
            f"{trip.returnFlight.origin}->{trip.returnFlight.destination}: "
            f"EUR {round(trip.totalPrice)} · {trip.nights} nights · score {trip.score}"
        )
        if trip.warnings:
            lines.append(f"  Warnings: {'; '.join(trip.warnings)}")
    lines.extend(["", token_note, f"You are receiving this because you saved a {settings.app_name} alert."])
    return "\n".join(lines)
