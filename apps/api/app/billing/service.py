from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.entitlements import (
    can_start_trial,
    csv_values,
    get_entitlements,
    get_user_plan,
    trial_days_remaining,
)
from app.billing.schemas import PlanInfo
from app.billing.usage import billing_usage_summary
from app.config import settings
from app.db.models import BillingSubscriptionDB, UserDB

PRO_STATUSES = {"active", "trialing", "past_due"}


def _pro_limits() -> dict:
    return {
        "savedSearchLimit": settings.triplet_pro_saved_search_limit,
        "aiSearchesPerMonth": settings.triplet_pro_ai_searches_per_month,
        "maxOriginAirports": settings.triplet_pro_max_origin_airports,
        "allowedAlertFrequencies": csv_values(settings.triplet_pro_alert_frequencies),
        "liveProviderAccess": True,
        "priorityAlerts": True,
    }


def available_plans() -> list[PlanInfo]:
    return [
        PlanInfo(
            plan="free",
            name="Free",
            priceLabel="€0",
            features=[
                "Basic trip search",
                "3 AI searches/month",
                "1 saved watch",
                "3 origin airports",
                "Weekly fare checks",
                "Email alerts",
            ],
            limits=get_entitlements(None),
        ),
        PlanInfo(
            plan="pro",
            name="Triplet Pro",
            priceLabel=settings.triplet_pro_price_monthly_label,
            priceYearlyLabel=settings.triplet_pro_price_yearly_label,
            features=[
                "100 AI searches/month",
                "10 saved watches",
                "8 origin airports",
                "Daily fare checks",
                "Open-jaw trip suggestions",
                "Deal and fit scores",
                "Travel profile",
                "Email alerts",
                "Dashboard",
            ],
            limits=_pro_limits(),
            stripeMonthlyPriceId=settings.stripe_price_pro_monthly,
            stripeYearlyPriceId=settings.stripe_price_pro_yearly,
        ),
    ]


def billing_status(db: Session, user: UserDB) -> dict:
    subscription = latest_subscription(db, user)
    current_period_end = subscription.current_period_end if subscription else None
    cancel_at_period_end = subscription.cancel_at_period_end if subscription else False
    plan = get_user_plan(user)
    return {
        "plan": plan,
        "subscriptionStatus": user.subscription_status,
        "currentPeriodEnd": current_period_end,
        "cancelAtPeriodEnd": cancel_at_period_end,
        "trialEndsAt": user.trial_ends_at if plan == "trial" else None,
        "trialDaysRemaining": trial_days_remaining(user),
        "limits": get_entitlements(user),
        "usage": billing_usage_summary(db, user),
        "canStartTrial": can_start_trial(user),
        "canUpgrade": plan in {"free", "trial"},
        "canManageBilling": bool(user.stripe_customer_id),
    }


class TrialError(ValueError):
    """Trial cannot be started (already used, or user already on Pro)."""


def start_trial(db: Session, user: UserDB) -> dict:
    """Start the one-time, no-card 7-day Pro trial for this user."""
    if get_user_plan(user) == "pro" and user.subscription_status in {"active", "past_due"}:
        raise TrialError("You already have Triplet Pro.")
    if not can_start_trial(user):
        raise TrialError("You've already used your free trial.")
    now = datetime.utcnow()
    user.trial_started_at = now
    user.trial_ends_at = now + timedelta(days=settings.triplet_trial_duration_days)
    user.trial_used = True
    user.plan = "trial"
    user.subscription_status = "trialing"
    user.updated_at = now
    db.commit()
    return billing_status(db, user)


def latest_subscription(db: Session, user: UserDB) -> BillingSubscriptionDB | None:
    return db.scalars(
        select(BillingSubscriptionDB)
        .where(BillingSubscriptionDB.user_id == user.id)
        .order_by(BillingSubscriptionDB.updated_at.desc())
    ).first()


def update_subscription_from_stripe_object(db: Session, subscription_obj: dict, event_type: str) -> BillingSubscriptionDB | None:
    customer_id = subscription_obj.get("customer")
    subscription_id = subscription_obj.get("id")
    if not customer_id:
        return None
    user_id = (subscription_obj.get("metadata") or {}).get("user_id")
    user = db.get(UserDB, user_id) if user_id else None
    if not user:
        user = db.scalar(select(UserDB).where(UserDB.stripe_customer_id == customer_id))
    if not user:
        return None
    user.stripe_customer_id = customer_id

    row = None
    if subscription_id:
        row = db.scalar(
            select(BillingSubscriptionDB).where(BillingSubscriptionDB.stripe_subscription_id == subscription_id)
        )
    if not row:
        row = BillingSubscriptionDB(
            id=str(uuid4()),
            user_id=user.id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan="pro",
            status="none",
        )
        db.add(row)

    row.stripe_customer_id = customer_id
    row.stripe_subscription_id = subscription_id
    row.stripe_price_id = _price_id(subscription_obj)
    row.plan = "pro"
    row.status = subscription_obj.get("status") or "none"
    row.current_period_start = _timestamp_to_datetime(subscription_obj.get("current_period_start"))
    row.current_period_end = _timestamp_to_datetime(subscription_obj.get("current_period_end"))
    row.cancel_at_period_end = bool(subscription_obj.get("cancel_at_period_end"))
    row.trial_end = _timestamp_to_datetime(subscription_obj.get("trial_end"))
    row.raw_last_event_type = event_type
    row.updated_at = datetime.utcnow()
    apply_user_plan(user, row.status)
    db.commit()
    return row


def apply_user_plan(user: UserDB, status: str) -> None:
    user.subscription_status = status
    user.plan = "pro" if status in PRO_STATUSES else "free"
    user.updated_at = datetime.utcnow()


def _price_id(subscription_obj: dict) -> str | None:
    items = ((subscription_obj.get("items") or {}).get("data") or [])
    if not items:
        return None
    price = items[0].get("price") or {}
    return price.get("id")


def _timestamp_to_datetime(value) -> datetime | None:
    if not value:
        return None
    return datetime.utcfromtimestamp(value)
