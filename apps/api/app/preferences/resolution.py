"""PreferenceResolutionService.

Merges the layers that decide what a search actually runs with, in priority:

    explicit search input  >  saved watch settings  >  travel profile  >  app defaults

The product rule: an explicit search always overrides the travel profile, and
the profile only fills what the search left blank. `resolve_search_preferences`
returns the resolved values plus a `sourceMap` naming where each value came
from ("search" | "watch" | "profile" | "default"), so the UI can show
"Using profile default" / "Overridden for this search".
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

# Spontaneity → default [earliest, latest] departure window as days from today.
# Both the legacy profile values and the richer new set map here, so existing
# profiles keep working while onboarding can offer the fuller scale.
SPONTANEITY_WINDOWS: dict[str, tuple[int, int]] = {
    "very_spontaneous": (0, 21),
    "soon": (7, 45),
    "flexible_monthly": (21, 90),
    "planner": (30, 180),
    "long_term_planner": (60, 270),
    # Legacy keys (kept for back-compat with existing saved profiles):
    "tomorrow": (0, 21),
    "next_week": (7, 45),
    "next_month": (21, 90),
    "planning_ahead": (30, 180),
}
DEFAULT_SPONTANEITY = "flexible_monthly"

APP_DEFAULTS: dict[str, Any] = {
    "minTripLengthDays": 3,
    "maxTripLengthDays": 8,
    "maxGroundTransferHours": 4.0,
    "tripStyle": "surprise me",
    "directOnly": False,
    "travelStyles": [],
    "comfortRules": {},
    "maxBudget": None,
    "dealSensitivity": "balanced",
}

# Field-name aliases so callers can pass either the raw profile attr or the
# search field name. The resolver reads whichever is present.
Source = str  # "search" | "watch" | "profile" | "default"


@dataclass
class ResolvedPreferences:
    values: dict[str, Any]
    sourceMap: dict[str, Source] = field(default_factory=dict)


def _present(value: Any) -> bool:
    """A value counts as 'provided' only if it's not None and not an empty list/dict/str."""
    if value is None:
        return False
    if isinstance(value, (list, dict, str)) and len(value) == 0:
        return False
    return True


def spontaneity_window(level: str | None, today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    lo, hi = SPONTANEITY_WINDOWS.get((level or DEFAULT_SPONTANEITY), SPONTANEITY_WINDOWS[DEFAULT_SPONTANEITY])
    return today + timedelta(days=lo), today + timedelta(days=hi)


def resolve_search_preferences(
    search_input: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    watch: dict[str, Any] | None = None,
    today: date | None = None,
) -> ResolvedPreferences:
    """Resolve a search's effective preferences across the four layers.

    All inputs are plain dicts (framework-agnostic). Keys are the search-field
    names; missing/empty values fall through to the next layer.
    """
    search_input = search_input or {}
    profile = profile or {}
    watch = watch or {}
    values: dict[str, Any] = {}
    source_map: dict[str, Source] = {}

    def resolve(field_name: str, profile_key: str | None = None, default: Any = None) -> None:
        profile_key = profile_key or field_name
        if _present(search_input.get(field_name)):
            values[field_name] = search_input[field_name]
            source_map[field_name] = "search"
        elif _present(watch.get(field_name)):
            values[field_name] = watch[field_name]
            source_map[field_name] = "watch"
        elif _present(profile.get(profile_key)):
            values[field_name] = profile[profile_key]
            source_map[field_name] = "profile"
        else:
            values[field_name] = default
            source_map[field_name] = "default"

    resolve("originAirports", "originAirports", default=[])
    resolve("minTripLengthDays", "preferredTripLengthMin", default=APP_DEFAULTS["minTripLengthDays"])
    resolve("maxTripLengthDays", "preferredTripLengthMax", default=APP_DEFAULTS["maxTripLengthDays"])
    resolve("travelStyles", "preferredTravelStyles", default=list(APP_DEFAULTS["travelStyles"]))
    resolve("maxBudget", "absoluteMaxBudget", default=APP_DEFAULTS["maxBudget"])
    resolve("dealSensitivity", "dealSensitivity", default=APP_DEFAULTS["dealSensitivity"])
    resolve("comfortRules", "comfortRules", default=dict(APP_DEFAULTS["comfortRules"]))
    resolve("maxGroundTransferHours", "maxGroundTransferHours", default=APP_DEFAULTS["maxGroundTransferHours"])
    resolve("tripStyle", "tripStyle", default=APP_DEFAULTS["tripStyle"])

    # Date range: explicit search dates win; otherwise derive from spontaneity.
    if _present(search_input.get("startDate")) and _present(search_input.get("endDate")):
        values["startDate"] = search_input["startDate"]
        values["endDate"] = search_input["endDate"]
        source_map["dateRange"] = "search"
    elif _present(watch.get("startDate")) and _present(watch.get("endDate")):
        values["startDate"] = watch["startDate"]
        values["endDate"] = watch["endDate"]
        source_map["dateRange"] = "watch"
    else:
        level = profile.get("spontaneityLevel") or profile.get("spontaneity")
        start, end = spontaneity_window(level, today)
        values["startDate"] = start
        values["endDate"] = end
        source_map["dateRange"] = "profile" if _present(level) else "default"

    return ResolvedPreferences(values=values, sourceMap=source_map)
