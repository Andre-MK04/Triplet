import calendar
from datetime import date, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.billing.entitlements import get_entitlements, get_user_plan, trial_is_active
from app.config import settings
from app.db.models import SavedSearchDB, UsageCounterDB, UserDB

AI_SEARCH = "ai_search"
SAVED_SEARCH_CREATED = "saved_search_created"


def calendar_month_period(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return today.replace(day=1), today.replace(day=last_day)


def ai_usage_period(user: UserDB, now: datetime | None = None) -> tuple[date, date]:
    """AI usage bucket for this user.

    Trial usage is counted across the whole 7-day trial window (a total cap);
    Free/Pro usage is counted per calendar month. Distinct buckets mean a Free
    user's monthly searches never bleed into their fresh trial allowance.
    """
    now = now or datetime.utcnow()
    if get_user_plan(user, now) == "trial" and trial_is_active(user, now):
        return user.trial_started_at.date(), user.trial_ends_at.date()  # type: ignore[union-attr]
    return calendar_month_period(now.date())


def _usage_count(db: Session, user_id: str, feature: str, period: tuple[date, date]) -> int:
    row = db.scalar(
        select(UsageCounterDB).where(
            UsageCounterDB.user_id == user_id,
            UsageCounterDB.feature == feature,
            UsageCounterDB.period_start == period[0],
            UsageCounterDB.period_end == period[1],
        )
    )
    return row.count if row else 0


def _increment(db: Session, user_id: str, feature: str, period: tuple[date, date]) -> int:
    row = db.scalar(
        select(UsageCounterDB).where(
            UsageCounterDB.user_id == user_id,
            UsageCounterDB.feature == feature,
            UsageCounterDB.period_start == period[0],
            UsageCounterDB.period_end == period[1],
        )
    )
    if not row:
        row = UsageCounterDB(
            id=str(uuid4()),
            user_id=user_id,
            feature=feature,
            period_start=period[0],
            period_end=period[1],
            count=0,
        )
        db.add(row)
    row.count += 1
    db.commit()
    return row.count


def get_ai_usage(db: Session, user: UserDB, now: datetime | None = None) -> int:
    return _usage_count(db, user.id, AI_SEARCH, ai_usage_period(user, now))


def record_ai_search(db: Session, user: UserDB, now: datetime | None = None) -> int:
    return _increment(db, user.id, AI_SEARCH, ai_usage_period(user, now))


def assert_ai_search_allowed(db: Session, user: UserDB | None) -> None:
    if not user:
        return
    entitlements = get_entitlements(user)
    limit = entitlements["aiSearchesPerMonth"]
    if get_ai_usage(db, user) >= limit:
        plan = entitlements["plan"]
        if plan == "trial":
            detail = f"You've used your {limit} trial AI searches. Upgrade to Pro to continue."
        elif plan == "pro":
            detail = f"You've used your {limit} Pro AI searches this month."
        else:
            detail = (
                f"You've used your {limit} free AI searches this month. "
                "Start your 7-day trial or upgrade to Pro."
            )
        raise HTTPException(status_code=402, detail=detail)


def assert_origin_airports_allowed(user: UserDB | None, count: int) -> None:
    if user is None:
        # Anonymous public search: allow the Vienna-region demo set.
        limit = settings.triplet_public_max_origin_airports
        if count > limit:
            raise HTTPException(
                status_code=402,
                detail=f"Public search allows up to {limit} origin airports. Sign in for more.",
            )
        return
    limit = get_entitlements(user)["maxOriginAirports"]
    if count > limit:
        raise HTTPException(
            status_code=402,
            detail=f"Your current plan allows up to {limit} origin airports.",
        )


def active_saved_search_count(db: Session, user: UserDB) -> int:
    return db.scalar(
        select(func.count(SavedSearchDB.id)).where(
            SavedSearchDB.user_id == user.id,
            SavedSearchDB.is_active.is_(True),
        )
    ) or 0


def assert_saved_search_allowed(db: Session, user: UserDB, frequency: str) -> None:
    entitlements = get_entitlements(user)
    if frequency not in entitlements["allowedAlertFrequencies"]:
        raise HTTPException(
            status_code=402,
            detail="Daily checks are available in the 7-day trial and Pro.",
        )
    limit = entitlements["savedSearchLimit"]
    if active_saved_search_count(db, user) >= limit:
        plan = entitlements["plan"]
        if plan == "trial":
            detail = f"You've reached the trial limit of {limit} saved watches. Upgrade to Pro for 10 saved watches."
        elif plan == "pro":
            detail = f"You've reached your Pro limit of {limit} saved watches."
        else:
            detail = (
                f"You've reached the Free limit of {limit} saved watch. "
                "Start your 7-day trial or upgrade to Pro."
            )
        raise HTTPException(status_code=402, detail=detail)


def billing_usage_summary(db: Session, user: UserDB) -> dict:
    entitlements = get_entitlements(user)
    return {
        "aiSearchesThisMonth": get_ai_usage(db, user),
        "aiSearchesPerMonth": entitlements["aiSearchesPerMonth"],
        "activeSavedSearches": active_saved_search_count(db, user),
        "savedSearchLimit": entitlements["savedSearchLimit"],
        "maxOriginAirports": entitlements["maxOriginAirports"],
        "dailyWatchChecks": entitlements["dailyWatchChecks"],
    }
