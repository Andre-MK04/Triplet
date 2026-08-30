from datetime import datetime

from app.config import settings
from app.db.models import UserDB

# Stripe subscription statuses that grant paid Pro access.
PRO_STATUSES = {"active", "trialing", "past_due"}

# Owner accounts have no practical cap. A large number rather than infinity keeps
# every existing comparison and JSON response working unchanged; the "unlimited"
# flag on the entitlements is what the UI reads, so nobody is shown a count.
UNLIMITED = 1_000_000_000


def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def is_owner_email(email: str | None) -> bool:
    if not email:
        return False
    allowed = {value.casefold() for value in csv_values(settings.triplet_owner_emails)}
    return email.strip().casefold() in allowed


def _is_paid_pro(user: UserDB) -> bool:
    # A real paid subscription: Pro plan with an active Stripe status. Our no-card
    # in-app trial is tracked via trial_ends_at, not Stripe, so it is handled
    # separately and never mistaken for paid Pro.
    return user.plan == "pro" and user.subscription_status in {"active", "past_due"}


def trial_is_active(user: UserDB | None, now: datetime | None = None) -> bool:
    if not user or not user.trial_ends_at:
        return False
    now = now or datetime.utcnow()
    return user.trial_ends_at > now


def get_user_plan(user: UserDB | None, now: datetime | None = None) -> str:
    """Effective plan. Owner beats everything, then paid Pro, then a live trial."""
    if not user:
        return "free"
    if is_owner_email(user.email):
        return "owner"
    if _is_paid_pro(user):
        return "pro"
    if trial_is_active(user, now):
        return "trial"
    return "free"


def trial_days_remaining(user: UserDB | None, now: datetime | None = None) -> int:
    if not trial_is_active(user, now):
        return 0
    now = now or datetime.utcnow()
    seconds = (user.trial_ends_at - now).total_seconds()  # type: ignore[union-attr]
    return max(0, -(-int(seconds) // 86400))  # ceil to whole days


def can_start_trial(user: UserDB | None, now: datetime | None = None) -> bool:
    if not user or _is_paid_pro(user) or trial_is_active(user, now):
        return False
    if is_owner_email(user.email):
        # Nothing to unlock; a trial would only downgrade what they already have.
        return False
    return not user.trial_used


def _limits_for(plan: str) -> dict:
    if plan == "owner":
        return {
            "plan": "owner",
            "savedSearchLimit": UNLIMITED,
            "aiSearchesPerMonth": UNLIMITED,
            "maxOriginAirports": UNLIMITED,
            "allowedAlertFrequencies": csv_values(settings.triplet_pro_alert_frequencies),
            "liveProviderAccess": True,
            "priorityAlerts": True,
        }
    if plan == "pro":
        return {
            "plan": "pro",
            "savedSearchLimit": settings.triplet_pro_saved_search_limit,
            "aiSearchesPerMonth": settings.triplet_pro_ai_searches_per_month,
            "maxOriginAirports": settings.triplet_pro_max_origin_airports,
            "allowedAlertFrequencies": csv_values(settings.triplet_pro_alert_frequencies),
            "liveProviderAccess": True,
            "priorityAlerts": True,
        }
    if plan == "trial":
        return {
            "plan": "trial",
            "savedSearchLimit": settings.triplet_trial_saved_search_limit,
            # Trial cap is a TOTAL across the 7-day window, not per calendar month.
            "aiSearchesPerMonth": settings.triplet_trial_ai_searches_total,
            "maxOriginAirports": settings.triplet_trial_max_origin_airports,
            "allowedAlertFrequencies": csv_values(settings.triplet_trial_alert_frequencies),
            "liveProviderAccess": True,
            "priorityAlerts": True,
        }
    return {
        "plan": "free",
        "savedSearchLimit": settings.triplet_free_saved_search_limit,
        "aiSearchesPerMonth": settings.triplet_free_ai_searches_per_month,
        "maxOriginAirports": settings.triplet_free_max_origin_airports,
        "allowedAlertFrequencies": csv_values(settings.triplet_free_alert_frequencies),
        "liveProviderAccess": False,
        "priorityAlerts": False,
    }


def get_entitlements(user: UserDB | None, now: datetime | None = None) -> dict:
    plan = get_user_plan(user, now)
    limits = _limits_for(plan)
    frequencies = limits["allowedAlertFrequencies"]
    limits["dailyWatchChecks"] = "daily" in frequencies
    limits["weeklyWatchChecks"] = "weekly" in frequencies
    limits["unlimited"] = plan == "owner"
    return limits
