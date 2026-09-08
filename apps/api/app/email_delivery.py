"""Verified email delivery events and minimal suppression policy."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import settings
from app.db.models import AlertDeliveryDB, EmailEventDB, EmailSuppressionDB

EmailCategory = Literal["account", "watch"]
TRACKED_EVENTS = {
    "email.bounced",
    "email.complained",
    "email.failed",
    "email.delivered",
    "email.delivery_delayed",
}


def recipient_hash(email: str) -> str:
    normalized = email.strip().lower()
    return hashlib.sha256(f"{settings.app_secret}:email:{normalized}".encode()).hexdigest()


def suppression_reason(db: Session, email: str) -> str | None:
    row = db.get(EmailSuppressionDB, recipient_hash(email))
    return row.reason if row else None


def is_suppressed(db: Session, email: str, category: EmailCategory) -> bool:
    """Hard bounces stop all mail; complaints stop optional watch mail.

    Password resets and account verification are user-requested security mail,
    so a complaint about a fare alert does not silently lock someone out.
    """

    reason = suppression_reason(db, email)
    return reason == "hard_bounce" or (reason == "complaint" and category == "watch")


async def process_resend_webhook(request: Request, db: Session) -> bool:
    secret = settings.resend_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Email webhook is not configured.")

    raw_body = await request.body()
    try:
        Webhook(secret).verify(raw_body, dict(request.headers))
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.") from exc

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

    event_id = request.headers.get("svix-id")
    event_type = payload.get("type")
    data = payload.get("data") or {}
    if not event_id or not isinstance(event_type, str) or not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")
    if db.get(EmailEventDB, event_id):
        return False

    provider_message_id = data.get("email_id") if isinstance(data.get("email_id"), str) else None
    recipients = data.get("to") if isinstance(data.get("to"), list) else []
    email = next((value for value in recipients if isinstance(value, str) and "@" in value), None)
    hashed = recipient_hash(email) if email else None
    occurred_at = _parse_datetime(payload.get("created_at"))
    db.add(EmailEventDB(
        svix_id=event_id,
        provider_message_id=provider_message_id,
        event_type=event_type[:80],
        recipient_hash=hashed,
        occurred_at=occurred_at,
    ))

    if provider_message_id and event_type in TRACKED_EVENTS:
        delivery = db.scalar(
            select(AlertDeliveryDB).where(AlertDeliveryDB.provider_message_id == provider_message_id)
        )
        if delivery:
            delivery.status = event_type.removeprefix("email.")

    reason = _suppression_reason(event_type, data)
    if hashed and reason:
        suppression = db.get(EmailSuppressionDB, hashed)
        if not suppression:
            suppression = EmailSuppressionDB(recipient_hash=hashed, reason=reason)
            db.add(suppression)
        # A complaint is the stronger user signal if both are ever received.
        if suppression.reason != "complaint" or reason == "complaint":
            suppression.reason = reason
        suppression.source_event_id = event_id

    try:
        db.commit()
    except IntegrityError:
        # Concurrent delivery of the same Svix event: the unique primary key is
        # the final idempotency guard.
        db.rollback()
        return False
    return True


def _suppression_reason(event_type: str, data: dict) -> str | None:
    if event_type == "email.complained":
        return "complaint"
    if event_type == "email.bounced":
        bounce = data.get("bounce") or {}
        if not isinstance(bounce, dict) or str(bounce.get("type", "Permanent")).lower() == "permanent":
            return "hard_bounce"
    return None


def _parse_datetime(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None
