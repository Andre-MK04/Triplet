import logging
import smtplib
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.alerts.email import EmailProviderError, build_email_provider
from app.alerts.templates import build_alert_html, build_alert_subject, build_alert_text
from app.alerts.schemas import (
    AlertPreviewResponse,
    AlertRunResponse,
    CreateSavedSearchRequest,
    SavedSearchResponse,
    UpdateSavedSearchRequest,
    WatchDeliveryStatus,
    WatchInsightsResponse,
    WatchPricePoint,
)
from app.alerts.token_utils import generate_token, hash_token, verify_token
from app.config import settings
from app.db.models import AlertDeliveryDB, AlertRunDB, SavedSearchDB, UserDB, UserTravelProfileDB
from app.observability import events
from app.db.repositories.airports_repository import AirportsRepository
from app.models import TripSearchRequest
from app.tools.base import ToolContext
from app.services.flight_search_service import FlightSearchService
from app.tools.registry import build_default_tool_registry
from app.tools.schemas import SearchTripsOutput

logger = logging.getLogger(__name__)


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

        # An account's email address is proof of nothing until the account has
        # proven it. Without `is_verified` here, anyone could sign up as someone
        # else's address, never confirm it, and have Triplet start mailing a
        # stranger who had confirmed nothing — the signed-in path skipped the
        # double opt-in that the anonymous path enforces.
        email_is_proven = bool(
            user
            and user.is_verified
            and request.email.strip().lower() == (user.email or "").strip().lower()
        )
        if not email_is_proven:
            self._guard_unverified_flood(request.email)

        manage_token = generate_token()
        unsubscribe_token = generate_token()
        verification_token = None if email_is_proven else generate_token()
        now = datetime.utcnow()
        row = SavedSearchDB(
            id=str(uuid4()),
            user_id=user.id if user else None,
            email=request.email,
            name=request.name,
            origin_airports=request.originAirports,
            destination_airports=request.destinationAirports,
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
            trigger_mode=request.triggerMode,
            is_active=True,
            manage_token_hash=hash_token(manage_token),
            unsubscribe_token_hash=hash_token(unsubscribe_token),
            email_verified_at=now if email_is_proven else None,
            verification_token_hash=hash_token(verification_token) if verification_token else None,
            verification_sent_at=None if email_is_proven else now,
            verification_expires_at=None
            if email_is_proven
            else now + timedelta(hours=settings.watch_verification_ttl_hours),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        events.watch_created(
            anonymous=user is None,
            trigger=request.triggerMode,
            frequency=request.frequency,
        )
        if verification_token:
            self._send_verification_email(row, verification_token)
        return self._to_response(row, manage_token=manage_token, unsubscribe_token=unsubscribe_token)

    # --- Email ownership ----------------------------------------------------

    def _guard_unverified_flood(self, email: str) -> None:
        """Stop one address being pointed at an unbounded pile of watches.

        Rate limiting caps how fast a single caller can create watches; this
        caps how many unconfirmed watches can accumulate against one inbox
        regardless of who created them or from where.
        """
        pending = self.db.scalar(
            select(func.count())
            .select_from(SavedSearchDB)
            .where(
                SavedSearchDB.email == email,
                SavedSearchDB.email_verified_at.is_(None),
                SavedSearchDB.is_active.is_(True),
            )
        )
        if (pending or 0) >= settings.watch_max_unverified_per_email:
            # Deliberately not phrased as "this address has N pending watches" —
            # that would confirm to a stranger that an address is in use here.
            raise AlertValidationError(
                "There are already unconfirmed watches waiting on this email address. "
                "Please confirm one of those first, or try again later."
            )

    def _send_verification_email(self, row: SavedSearchDB, verification_token: str) -> None:
        """Ask the address to confirm it wants this watch.

        A send failure must not lose the watch — the row is already committed
        and the traveller can ask for a fresh link — so this never raises.
        """
        link = f"{settings.alerts_public_base_url.rstrip('/')}/watch/confirm?token={verification_token}"
        subject = "Confirm your Triplet watch"
        text_body = (
            "Someone asked Triplet to watch flight prices and send the results to this address.\n\n"
            f"If that was you, confirm it here:\n{link}\n\n"
            f"The link works for {settings.watch_verification_ttl_hours} hours. "
            "If it wasn't you, ignore this email — nothing was set up and we won't email you again."
        )
        html_body = (
            "<p>Someone asked Triplet to watch flight prices and send the results to this address.</p>"
            f'<p>If that was you, <a href="{link}">confirm your watch</a>.</p>'
            f"<p>The link works for {settings.watch_verification_ttl_hours} hours. "
            "If it wasn't you, ignore this email — nothing was set up and we won't email you again.</p>"
        )
        try:
            build_email_provider().send_email(row.email, subject, html_body, text_body)
        except (EmailProviderError, smtplib.SMTPException, OSError):
            # Never log the token or the link: both are the credential itself.
            logger.exception("watch_verification_email_failed saved_search_id=%s", row.id)

    def verify_saved_search(self, token: str) -> SavedSearchResponse:
        """Activate a watch from its emailed confirmation link.

        Single use: the token hash is cleared on success, so a link that leaks
        from a mailbox later cannot re-activate anything.
        """
        if not token:
            raise SavedSearchNotFoundError("This confirmation link is not valid.")
        row = self.db.scalar(
            select(SavedSearchDB).where(SavedSearchDB.verification_token_hash == hash_token(token))
        )
        if row is None:
            raise SavedSearchNotFoundError("This confirmation link is not valid or has already been used.")
        if row.verification_expires_at and row.verification_expires_at < datetime.utcnow():
            raise AlertValidationError(
                "This confirmation link has expired. Create the watch again to get a fresh link."
            )

        row.email_verified_at = datetime.utcnow()
        row.verification_token_hash = None
        row.verification_expires_at = None
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        events.watch_verified()
        return self._to_response(row)

    def resend_verification(self, saved_search_id: str, token: str) -> None:
        """Send a fresh confirmation link, invalidating the previous one."""
        row = self._get_authorized(saved_search_id, token)
        if row.email_verified_at is not None:
            return  # Already confirmed; nothing to send and nothing to reveal.
        verification_token = generate_token()
        now = datetime.utcnow()
        row.verification_token_hash = hash_token(verification_token)
        row.verification_sent_at = now
        row.verification_expires_at = now + timedelta(hours=settings.watch_verification_ttl_hours)
        self.db.commit()
        self.db.refresh(row)
        self._send_verification_email(row, verification_token)

    def purge_stale_unverified(self) -> int:
        """Delete watches whose address was never confirmed.

        An unconfirmed watch is a record of an address someone typed, not a
        relationship anyone agreed to — it should not be retained forever.
        """
        cutoff = datetime.utcnow() - timedelta(hours=settings.watch_unverified_retention_hours)
        stale = list(
            self.db.scalars(
                select(SavedSearchDB).where(
                    SavedSearchDB.email_verified_at.is_(None),
                    SavedSearchDB.created_at < cutoff,
                )
            ).all()
        )
        for row in stale:
            self.db.delete(row)
        if stale:
            self.db.commit()
        return len(stale)

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

    def deactivate_user_saved_search(self, user: UserDB, saved_search_id: str) -> SavedSearchResponse:
        row = self._get_user_saved_search(user, saved_search_id)
        row.is_active = False
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return self._to_response(row)

    def get_user_saved_search(self, user: UserDB, saved_search_id: str) -> SavedSearchResponse:
        row = self._get_user_saved_search(user, saved_search_id)
        return self._to_response(row)

    def get_user_saved_search_insights(self, user: UserDB, saved_search_id: str) -> WatchInsightsResponse:
        row = self._get_user_saved_search(user, saved_search_id)
        runs = list(
            self.db.scalars(
                select(AlertRunDB)
                .where(AlertRunDB.saved_search_id == row.id)
                .order_by(AlertRunDB.started_at.desc())
                .limit(30)
            )
        )
        deliveries = list(
            self.db.scalars(
                select(AlertDeliveryDB)
                .where(AlertDeliveryDB.saved_search_id == row.id)
                .order_by(AlertDeliveryDB.created_at.desc())
                .limit(8)
            )
        )
        total_checks = self.db.scalar(
            select(func.count(AlertRunDB.id)).where(AlertRunDB.saved_search_id == row.id)
        ) or 0
        successful_checks = self.db.scalar(
            select(func.count(AlertRunDB.id))
            .where(AlertRunDB.saved_search_id == row.id)
            .where(AlertRunDB.status.in_({"success", "no_results"}))
        ) or 0
        notification_count = self.db.scalar(
            select(func.count(AlertDeliveryDB.id)).where(AlertDeliveryDB.saved_search_id == row.id)
        ) or 0
        prices = [run.best_price for run in runs if run.best_price is not None]
        chronological_prices = list(reversed(prices))
        change_from_previous = None
        if len(chronological_prices) >= 2:
            change_from_previous = round(chronological_prices[-1] - chronological_prices[-2], 2)
        current_best = prices[0] if prices else row.last_best_price
        return WatchInsightsResponse(
            savedSearchId=row.id,
            alertTriggerMode=self._alert_trigger_mode(row),
            totalChecks=total_checks,
            successfulChecks=successful_checks,
            notificationCount=notification_count,
            currentBestPrice=current_best,
            lowestObservedPrice=min(prices) if prices else current_best,
            averageObservedPrice=round(sum(prices) / len(prices), 2) if prices else current_best,
            changeFromPrevious=change_from_previous,
            budgetHeadroom=round(row.max_budget - current_best, 2) if current_best is not None else None,
            history=[
                WatchPricePoint(
                    checkedAt=run.finished_at or run.started_at,
                    bestPrice=run.best_price,
                    resultCount=run.result_count,
                    status=run.status,
                )
                for run in reversed(runs)
            ],
            deliveries=[
                WatchDeliveryStatus(
                    sentAt=delivery.created_at,
                    status=delivery.status,
                    provider=delivery.provider,
                    subject=delivery.subject,
                )
                for delivery in deliveries
            ],
        )

    def resume_user_saved_search(self, user: UserDB, saved_search_id: str) -> SavedSearchResponse:
        row = self._get_user_saved_search(user, saved_search_id)
        row.is_active = True
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return self._to_response(row)

    def update_user_saved_search(
        self,
        user: UserDB,
        saved_search_id: str,
        request: UpdateSavedSearchRequest,
    ) -> SavedSearchResponse:
        row = self._get_user_saved_search(user, saved_search_id)
        if request.name is not None:
            row.name = request.name
        if request.originAirports is not None:
            row.origin_airports = request.originAirports
        if request.destinationAirports is not None:
            # An empty list clears the filter back to "anywhere".
            row.destination_airports = request.destinationAirports or None
        if request.startDate is not None:
            row.start_date = request.startDate
        if request.endDate is not None:
            row.end_date = request.endDate
        if request.minTripLengthDays is not None:
            row.min_trip_length_days = request.minTripLengthDays
        if request.maxTripLengthDays is not None:
            row.max_trip_length_days = request.maxTripLengthDays
        if request.maxBudget is not None:
            row.max_budget = request.maxBudget
        if request.maxGroundTransferHours is not None:
            row.max_ground_transfer_hours = request.maxGroundTransferHours
        if request.tripStyle is not None:
            row.trip_style = request.tripStyle
        if request.directOnly is not None:
            row.direct_only = request.directOnly
        if request.includeBaggage is not None:
            row.include_baggage = request.includeBaggage
        if request.frequency is not None:
            row.frequency = request.frequency
        if request.triggerMode is not None:
            row.trigger_mode = request.triggerMode
        self._validate_row(row)
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return self._to_response(row)

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
        query = select(SavedSearchDB).where(
            SavedSearchDB.is_active.is_(True),
            # An address that never confirmed is not a subscriber.
            SavedSearchDB.email_verified_at.is_not(None),
        )
        if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
            # Overlapping runs are the normal case for a scheduler whose ticks
            # take longer than its interval. SKIP LOCKED lets a second runner
            # take different watches rather than queue behind the first or race
            # it. The duplicate *send* is already impossible — see
            # _claim_notification_slot — this stops the duplicate *work*, which
            # costs real provider calls.
            query = query.with_for_update(skip_locked=True)
        rows = self.db.scalars(query).all()
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

            # Claim the notification slot before sending, not after. Deciding to
            # send and recording that it was sent used to be separated by the
            # send itself, with nothing committed in between — so two runners
            # could both read the same last_notified_at, both pass the cooldown,
            # and both email the same traveller the same deal.
            if should_notify and self._claim_notification_slot(row):
                self._send_delivery(row, run, output)
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
            events.alert_run(
                status=run.status,
                result_count=run.result_count,
                notified=notification_sent,
            )

        return AlertRunResponse(
            savedSearchId=row.id,
            status=run.status,
            resultCount=run.result_count,
            bestPrice=run.best_price,
            notificationSent=notification_sent,
            warnings=warnings,
        )

    def _send_delivery(self, row: SavedSearchDB, run: AlertRunDB, output: SearchTripsOutput) -> None:
        # The last gate before an email is addressed. list_due_saved_searches
        # already filters these out, but delivery is where the irreversible
        # side effect happens, so it refuses on its own authority too.
        if row.email_verified_at is None:
            raise AlertValidationError(
                "This watch's email address has not been confirmed, so no alert was sent."
            )
        city_names = {airport.code: airport.city for airport in AirportsRepository(self.db).list_airports()}
        manage_note = (
            "Manage this watch on your Triplet dashboard."
            if row.user_id
            else "Use your manage/unsubscribe links from the alert creation response."
        )
        subject = build_alert_subject(row, output, city_names)
        text_body = build_alert_text(row, output, city_names, manage_note)
        html_body = build_alert_html(row, output, city_names, manage_note)
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
        # Pass ownership so scoring can use the owner's travel profile (fit score).
        context = ToolContext(
            db=self.db,
            user_id=row.user_id,
            flight_search_service=FlightSearchService(db=self.db, cache_only=True),
        )
        result = self.registry.run_tool("search_trips", request.model_dump(mode="json"), context)
        return SearchTripsOutput.model_validate(result)

    def _validate_request(self, request: CreateSavedSearchRequest) -> None:
        if request.endDate < request.startDate:
            raise AlertValidationError("endDate must be on or after startDate.")
        if (request.endDate - request.startDate).days > 180:
            raise AlertValidationError("Saved alert date range cannot exceed 180 days.")
        if request.maxTripLengthDays < request.minTripLengthDays:
            raise AlertValidationError("maxTripLengthDays must be greater than or equal to minTripLengthDays.")
        known = {airport.code for airport in AirportsRepository(self.db).list_origin_candidates()}
        invalid = [code for code in request.originAirports if code not in known]
        if invalid:
            raise AlertValidationError(f"Unknown origin airport code(s): {', '.join(invalid)}.")
        if request.destinationAirports:
            from app.data.flight_places import is_flightable_place

            invalid_destinations = [code for code in request.destinationAirports if not is_flightable_place(code)]
            if invalid_destinations:
                raise AlertValidationError(
                    f"Unknown destination code(s): {', '.join(invalid_destinations)}."
                )

    def _validate_row(self, row: SavedSearchDB) -> None:
        request = CreateSavedSearchRequest(
            email=row.email,
            name=row.name,
            originAirports=row.origin_airports,
            destinationAirports=row.destination_airports,
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
        )
        self._validate_request(request)

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

    def _claim_notification_slot(self, row: SavedSearchDB) -> bool:
        """Take exclusive right to notify this watch now. False if someone else has it.

        One conditional UPDATE, committed immediately so a concurrent runner
        sees it: the cooldown is re-tested in the same statement that stamps it,
        which no interleaving can get between. Works identically on PostgreSQL
        and SQLite because it relies on row-level atomicity rather than on any
        dialect's locking syntax.

        A failed send deliberately keeps the claim rather than releasing it. We
        cannot tell whether the provider accepted the message before failing, and
        a missed alert is recoverable on the next run while a duplicate is not.
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=settings.alerts_min_hours_between_notifications)
        claimed = self.db.execute(
            update(SavedSearchDB)
            .where(SavedSearchDB.id == row.id)
            .where(
                or_(
                    SavedSearchDB.last_notified_at.is_(None),
                    SavedSearchDB.last_notified_at < cutoff,
                )
            )
            .values(last_notified_at=now)
        ).rowcount
        self.db.commit()
        if claimed:
            row.last_notified_at = now
            return True
        events.alert_duplicate_prevented(saved_search_id=row.id)
        return False

    def _should_notify(self, row: SavedSearchDB, best_price: float) -> bool:
        if row.last_notified_at:
            cooldown = timedelta(hours=settings.alerts_min_hours_between_notifications)
            if row.last_notified_at > datetime.utcnow() - cooldown:
                return False
        mode = self._alert_trigger_mode(row)
        previous_price = row.last_best_price

        if mode == "price_drop":
            if previous_price is None:
                return False
            required_drop = max(10, previous_price * 0.05)
            return best_price <= previous_price - required_drop

        if mode == "route_deal":
            previous_prices = list(
                self.db.scalars(
                    select(AlertRunDB.best_price)
                    .where(AlertRunDB.saved_search_id == row.id)
                    .where(AlertRunDB.best_price.is_not(None))
                    .order_by(AlertRunDB.started_at.desc())
                    .limit(30)
                )
            )
            if len(previous_prices) >= 3:
                route_average = sum(previous_prices) / len(previous_prices)
                return best_price <= route_average * 0.85
            return best_price <= row.max_budget * 0.8

        if mode == "below_budget":
            if best_price > row.max_budget:
                return False
            return previous_price is None or best_price < previous_price

        if row.last_notified_at is None or previous_price is None:
            return True
        return best_price <= previous_price - 10

    def _alert_trigger_mode(self, row: SavedSearchDB) -> str:
        """What makes this watch worth an email.

        The watch's own choice wins. Failing that the account's preference
        applies, and failing that "any" — which is what every watch did before a
        watch could choose, so nothing changes for one that never did.
        """
        if row.trigger_mode:
            return row.trigger_mode
        if not row.user_id:
            return "any"
        profile = self.db.get(UserTravelProfileDB, row.user_id)
        return profile.alert_trigger_mode if profile and profile.alert_trigger_mode else "any"

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
        destinationAirports=row.destination_airports,
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
        destinationAirports=row.destination_airports,
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
        triggerMode=row.trigger_mode,
        isActive=row.is_active,
        createdAt=row.created_at,
        lastCheckedAt=row.last_checked_at,
        lastNotifiedAt=row.last_notified_at,
        lastBestPrice=row.last_best_price,
        lastBestTripId=row.last_best_trip_id,
        manageUrl=f"{base_url}/alerts/{row.id}?token={manage_token}" if manage_token else None,
        unsubscribeUrl=f"{base_url}/alerts/{row.id}/unsubscribe?token={unsubscribe_token}" if unsubscribe_token else None,
    )
