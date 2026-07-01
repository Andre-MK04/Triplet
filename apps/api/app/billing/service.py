from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.entitlements import get_entitlements, get_user_plan
from app.billing.schemas import PlanInfo
from app.billing.usage import billing_usage_summary
from app.config import settings
from app.db.models import BillingSubscriptionDB, UserDB

PRO_STATUSES = {"active", "trialing", "past_due"}


def available_plans() -> list[PlanInfo]:
    return [
        PlanInfo(
            plan="free",
            name="Free",
            priceLabel="€0",
            features=["Basic trip search", "3 saved alerts", "5 AI searches/day", "Daily alerts"],
            limits=get_entitlements(None),
        ),
        PlanInfo(
            plan="pro",
            name="Triplet Pro",
            priceLabel="Monthly or yearly",
            features=["30 saved alerts", "100 AI searches/day", "More origin airports", "Weekly alerts"],
            limits={
                "savedSearchLimit": settings.triplet_pro_saved_search_limit,
                "aiSearchesPerDay": settings.triplet_pro_ai_searches_per_day,
                "maxOriginAirports": settings.triplet_pro_max_origin_airports,
                "allowedAlertFrequencies": [x.strip() for x in settings.triplet_pro_alert_frequencies.split(",")],
                "liveProviderAccess": True,
                "priorityAlerts": True,
            },
            stripeMonthlyPriceId=settings.stripe_price_pro_monthly,
            stripeYearlyPriceId=settings.stripe_price_pro_yearly,
        ),
    ]


def billing_status(db: Session, user: UserDB) -> dict:
    subscription = latest_subscription(db, user)
    current_period_end = subscription.current_period_end if subscription else None
    cancel_at_period_end = subscription.cancel_at_period_end if subscription else False
    return {
        "plan": get_user_plan(user),
        "subscriptionStatus": user.subscription_status,
        "currentPeriodEnd": current_period_end,
        "cancelAtPeriodEnd": cancel_at_period_end,
        "limits": get_entitlements(user),
        "usage": billing_usage_summary(db, user),
        "canUpgrade": get_user_plan(user) == "free",
        "canManageBilling": bool(user.stripe_customer_id),
    }


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
