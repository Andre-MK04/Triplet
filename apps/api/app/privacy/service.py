"""GDPR data-subject rights: export (Art. 15 access) and erasure (Art. 17).

export_user_data returns everything we hold that is linked to the account, with
no secrets (password hashes, token hashes, provider tokens are never included).

erase_user erases the account and every table that links to it, in FK-safe
order. Audit rows are anonymised (user_id nulled) rather than deleted, so the
security trail survives without the personal identifier — a recognised GDPR
pseudonymisation approach. The erasure itself is audited (action only, no PII).

When a NEW user-linked table is introduced, add it to both functions AND to
test_privacy.py's "no rows remain" assertion.
"""

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    AlertDeliveryDB,
    AlertRunDB,
    AuditEventDB,
    BillingSubscriptionDB,
    EmailVerificationTokenDB,
    PasswordResetTokenDB,
    RefreshTokenSessionDB,
    SavedSearchDB,
    TripSuggestionDB,
    UsageCounterDB,
    UserDB,
    UserOAuthAccountDB,
    UserTravelProfileDB,
)


def export_user_data(db: Session, user: UserDB) -> dict:
    profile = db.get(UserTravelProfileDB, user.id)
    saved = db.scalars(select(SavedSearchDB).where(SavedSearchDB.user_id == user.id)).all()
    oauth = db.scalars(select(UserOAuthAccountDB).where(UserOAuthAccountDB.user_id == user.id)).all()
    suggestions = db.scalars(select(TripSuggestionDB).where(TripSuggestionDB.user_id == user.id)).all()
    usage = db.scalars(select(UsageCounterDB).where(UsageCounterDB.user_id == user.id)).all()

    return {
        "exportedAt": _now_iso(),
        "account": {
            "id": user.id,
            "email": user.email,
            "displayName": user.display_name,
            "plan": user.plan,
            "createdAt": _iso(user.created_at),
            "lastLoginAt": _iso(user.last_login_at),
        },
        "travelProfile": _profile_dict(profile) if profile else None,
        "savedSearches": [
            {
                "name": s.name,
                "originAirports": s.origin_airports,
                "destinationAirports": s.destination_airports,
                "startDate": _iso(s.start_date),
                "endDate": _iso(s.end_date),
                "maxBudget": s.max_budget,
                "frequency": s.frequency,
                "isActive": s.is_active,
                "createdAt": _iso(s.created_at),
            }
            for s in saved
        ],
        "linkedLogins": [{"provider": o.provider, "email": o.email} for o in oauth],
        "tripSuggestions": [
            {"title": t.title, "totalPrice": t.total_price, "createdAt": _iso(t.created_at)}
            for t in suggestions
        ],
        "usage": [
            {"feature": u.feature, "periodStart": _iso(u.period_start), "count": u.count}
            for u in usage
        ],
        "note": (
            "This is all personal data linked to your Triplet account. It excludes "
            "security material we never expose (password and token hashes)."
        ),
    }


def erase_user(db: Session, user: UserDB, request=None) -> None:
    user_id = user.id
    # Alerts hang off saved searches (FK), so clear them before the searches.
    saved_ids = list(
        db.scalars(select(SavedSearchDB.id).where(SavedSearchDB.user_id == user_id)).all()
    )
    if saved_ids:
        db.execute(delete(AlertDeliveryDB).where(AlertDeliveryDB.saved_search_id.in_(saved_ids)))
        db.execute(delete(AlertRunDB).where(AlertRunDB.saved_search_id.in_(saved_ids)))

    for model in (
        SavedSearchDB,
        TripSuggestionDB,
        UserTravelProfileDB,
        UserOAuthAccountDB,
        RefreshTokenSessionDB,
        PasswordResetTokenDB,
        EmailVerificationTokenDB,
        UsageCounterDB,
        BillingSubscriptionDB,
    ):
        db.execute(delete(model).where(model.user_id == user_id))

    # Anonymise the security audit trail rather than delete it.
    db.execute(update(AuditEventDB).where(AuditEventDB.user_id == user_id).values(user_id=None))

    db.delete(user)
    db.commit()

    # Best-effort: record that an erasure happened (no PII), on a fresh transaction.
    try:
        from app.audit import record_audit_event

        record_audit_event(db, "privacy.account_erased", request=request, commit=True)
    except Exception:  # noqa: BLE001 - auditing must never block erasure
        db.rollback()


def _profile_dict(profile: UserTravelProfileDB) -> dict:
    return {
        "homeLocation": profile.home_location,
        "originAirports": profile.origin_airports,
        "preferredTripTypes": profile.preferred_trip_types,
        "budgetComfortZone": profile.budget_comfort_zone,
        "comfortRules": profile.comfort_rules,
        "notificationFrequency": profile.notification_frequency,
    }


def _iso(value):
    return value.isoformat() if value is not None else None


def _now_iso() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat() + "Z"
