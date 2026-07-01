from app.config import settings
from app.db.models import UserDB

PRO_STATUSES = {"active", "trialing", "past_due"}


def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def get_user_plan(user: UserDB | None) -> str:
    if not user:
        return "free"
    if user.plan == "pro" and user.subscription_status in PRO_STATUSES:
        return "pro"
    return "free"


def get_entitlements(user: UserDB | None) -> dict:
    plan = get_user_plan(user)
    if plan == "pro":
        return {
            "plan": "pro",
            "savedSearchLimit": settings.triplet_pro_saved_search_limit,
            "aiSearchesPerDay": settings.triplet_pro_ai_searches_per_day,
            "maxOriginAirports": settings.triplet_pro_max_origin_airports,
            "allowedAlertFrequencies": csv_values(settings.triplet_pro_alert_frequencies),
            "liveProviderAccess": True,
            "priorityAlerts": True,
        }
    return {
        "plan": "free",
        "savedSearchLimit": settings.triplet_free_saved_search_limit,
        "aiSearchesPerDay": settings.triplet_free_ai_searches_per_day,
        "maxOriginAirports": settings.triplet_free_max_origin_airports,
        "allowedAlertFrequencies": csv_values(settings.triplet_free_alert_frequencies),
        "liveProviderAccess": False,
        "priorityAlerts": False,
    }
