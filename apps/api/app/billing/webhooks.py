from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.service import apply_user_plan, update_subscription_from_stripe_object
from app.db.models import BillingEventDB, BillingSubscriptionDB, UserDB

HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
}


def process_stripe_event(db: Session, event: dict) -> str:
    event_id = event.get("id")
    event_type = event.get("type") or "unknown"
    if not event_id:
        return "ignored"
    existing = db.scalar(select(BillingEventDB).where(BillingEventDB.stripe_event_id == event_id))
    if existing:
        return existing.processing_status

    event_row = BillingEventDB(
        id=str(uuid4()),
        stripe_event_id=event_id,
        event_type=event_type,
        processed_at=datetime.utcnow(),
        processing_status="success" if event_type in HANDLED_EVENTS else "ignored",
    )
    db.add(event_row)
    try:
        obj = (event.get("data") or {}).get("object") or {}
        if event_type == "checkout.session.completed":
            _handle_checkout_session_completed(db, obj)
        elif event_type.startswith("customer.subscription."):
            update_subscription_from_stripe_object(db, obj, event_type)
        elif event_type == "invoice.payment_failed":
            _handle_invoice_payment_failed(db, obj)
        elif event_type == "invoice.payment_succeeded":
            _handle_invoice_payment_succeeded(db, obj)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - webhook processing must persist failure rows.
        db.rollback()
        event_row.processing_status = "error"
        event_row.error_message = str(exc)
        db.add(event_row)
        db.commit()
        return "error"
    return event_row.processing_status


def _handle_checkout_session_completed(db: Session, session: dict) -> None:
    user_id = (session.get("metadata") or {}).get("user_id")
    user = db.get(UserDB, user_id) if user_id else None
    if not user and session.get("customer"):
        user = db.scalar(select(UserDB).where(UserDB.stripe_customer_id == session.get("customer")))
    if not user:
        return
    user.stripe_customer_id = session.get("customer") or user.stripe_customer_id
    if session.get("subscription"):
        subscription_id = session.get("subscription")
        row = db.scalar(
            select(BillingSubscriptionDB).where(BillingSubscriptionDB.stripe_subscription_id == subscription_id)
        )
        if not row:
            row = BillingSubscriptionDB(
                id=str(uuid4()),
                user_id=user.id,
                stripe_customer_id=user.stripe_customer_id,
                stripe_subscription_id=subscription_id,
                stripe_price_id=None,
                plan="pro",
                status="active",
                cancel_at_period_end=False,
                raw_last_event_type="checkout.session.completed",
            )
            db.add(row)
        user.subscription_status = "active"
        user.plan = "pro"
        user.updated_at = datetime.utcnow()


def _handle_invoice_payment_failed(db: Session, invoice: dict) -> None:
    customer_id = invoice.get("customer")
    user = db.scalar(select(UserDB).where(UserDB.stripe_customer_id == customer_id)) if customer_id else None
    if user:
        apply_user_plan(user, "past_due")


def _handle_invoice_payment_succeeded(db: Session, invoice: dict) -> None:
    customer_id = invoice.get("customer")
    user = db.scalar(select(UserDB).where(UserDB.stripe_customer_id == customer_id)) if customer_id else None
    if user and user.subscription_status == "past_due":
        apply_user_plan(user, "active")
