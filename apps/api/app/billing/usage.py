from datetime import date
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.billing.entitlements import get_entitlements
from app.db.models import SavedSearchDB, UsageCounterDB, UserDB

AI_SEARCH = "ai_search"
SAVED_SEARCH_CREATED = "saved_search_created"


def today_period() -> tuple[date, date]:
    today = date.today()
    return today, today


def get_daily_usage(db: Session, user_id: str, feature: str) -> int:
    period_start, period_end = today_period()
    row = db.scalar(
        select(UsageCounterDB).where(
            UsageCounterDB.user_id == user_id,
            UsageCounterDB.feature == feature,
            UsageCounterDB.period_start == period_start,
            UsageCounterDB.period_end == period_end,
        )
    )
    return row.count if row else 0


def increment_usage(db: Session, user_id: str, feature: str) -> int:
    period_start, period_end = today_period()
    row = db.scalar(
        select(UsageCounterDB).where(
            UsageCounterDB.user_id == user_id,
            UsageCounterDB.feature == feature,
            UsageCounterDB.period_start == period_start,
            UsageCounterDB.period_end == period_end,
        )
    )
    if not row:
        row = UsageCounterDB(
            id=str(uuid4()),
            user_id=user_id,
            feature=feature,
            period_start=period_start,
            period_end=period_end,
            count=0,
        )
        db.add(row)
    row.count += 1
    db.commit()
    return row.count


def assert_ai_search_allowed(db: Session, user: UserDB | None) -> None:
    if not user:
        return
    entitlements = get_entitlements(user)
    used = get_daily_usage(db, user.id, AI_SEARCH)
    if used >= entitlements["aiSearchesPerDay"]:
        raise HTTPException(
            status_code=402,
            detail="You've reached the free AI search limit for today. Upgrade to Triplet Pro for more searches.",
        )


def assert_origin_airports_allowed(user: UserDB | None, count: int) -> None:
    entitlements = get_entitlements(user)
    if count > entitlements["maxOriginAirports"]:
        raise HTTPException(
            status_code=402,
            detail=f"Your plan allows up to {entitlements['maxOriginAirports']} origin airports.",
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
            detail="Weekly alerts are available on Triplet Pro.",
        )
    if active_saved_search_count(db, user) >= entitlements["savedSearchLimit"]:
        raise HTTPException(
            status_code=402,
            detail="You've reached your saved alert limit. Upgrade to Triplet Pro for more saved alerts.",
        )


def billing_usage_summary(db: Session, user: UserDB) -> dict:
    entitlements = get_entitlements(user)
    return {
        "aiSearchesToday": get_daily_usage(db, user.id, AI_SEARCH),
        "aiSearchesPerDay": entitlements["aiSearchesPerDay"],
        "activeSavedSearches": active_saved_search_count(db, user),
        "savedSearchLimit": entitlements["savedSearchLimit"],
    }
