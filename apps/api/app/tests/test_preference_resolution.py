from datetime import date

from app.preferences.resolution import (
    DEFAULT_SPONTANEITY,
    resolve_search_preferences,
    spontaneity_window,
)

PROFILE = {
    "originAirports": ["VIE", "ZAG"],
    "preferredTripLengthMin": 4,
    "preferredTripLengthMax": 9,
    "preferredTravelStyles": ["food", "culture"],
    "absoluteMaxBudget": 250.0,
    "dealSensitivity": "strict",
    "comfortRules": {"direct_only": "require"},
    "spontaneityLevel": "planner",
}


def test_explicit_search_overrides_profile():
    resolved = resolve_search_preferences(
        {"originAirports": ["BUD"], "maxBudget": 120, "travelStyles": ["beach"]},
        PROFILE,
    )
    assert resolved.values["originAirports"] == ["BUD"]
    assert resolved.values["maxBudget"] == 120
    assert resolved.values["travelStyles"] == ["beach"]
    assert resolved.sourceMap["originAirports"] == "search"
    assert resolved.sourceMap["maxBudget"] == "search"
    assert resolved.sourceMap["travelStyles"] == "search"


def test_profile_fills_missing_values():
    resolved = resolve_search_preferences({}, PROFILE)
    assert resolved.values["originAirports"] == ["VIE", "ZAG"]
    assert resolved.values["maxBudget"] == 250.0
    assert resolved.values["travelStyles"] == ["food", "culture"]
    assert resolved.values["comfortRules"] == {"direct_only": "require"}
    assert resolved.sourceMap["originAirports"] == "profile"
    assert resolved.sourceMap["maxBudget"] == "profile"
    assert resolved.sourceMap["comfortRules"] == "profile"


def test_defaults_fill_missing_profile_and_search():
    resolved = resolve_search_preferences({}, {})
    assert resolved.values["maxBudget"] is None
    assert resolved.values["dealSensitivity"] == "balanced"
    assert resolved.values["travelStyles"] == []
    assert resolved.sourceMap["maxBudget"] == "default"
    assert resolved.sourceMap["travelStyles"] == "default"
    assert resolved.sourceMap["dateRange"] == "default"


def test_watch_layer_sits_between_search_and_profile():
    resolved = resolve_search_preferences(
        {},
        PROFILE,
        watch={"originAirports": ["TRS"], "maxBudget": 300},
    )
    assert resolved.values["originAirports"] == ["TRS"]
    assert resolved.sourceMap["originAirports"] == "watch"
    assert resolved.values["maxBudget"] == 300
    assert resolved.sourceMap["maxBudget"] == "watch"


def test_spontaneity_creates_default_date_window():
    today = date(2026, 1, 1)
    resolved = resolve_search_preferences({}, {"spontaneityLevel": "very_spontaneous"}, today=today)
    assert resolved.values["startDate"] == date(2026, 1, 1)
    assert resolved.values["endDate"] == date(2026, 1, 22)  # +21 days
    assert resolved.sourceMap["dateRange"] == "profile"


def test_explicit_dates_override_spontaneity():
    today = date(2026, 1, 1)
    resolved = resolve_search_preferences(
        {"startDate": date(2026, 3, 1), "endDate": date(2026, 3, 10)},
        {"spontaneityLevel": "long_term_planner"},
        today=today,
    )
    assert resolved.values["startDate"] == date(2026, 3, 1)
    assert resolved.values["endDate"] == date(2026, 3, 10)
    assert resolved.sourceMap["dateRange"] == "search"


def test_spontaneity_window_default_and_legacy_keys():
    today = date(2026, 1, 1)
    assert spontaneity_window("next_week", today) == (date(2026, 1, 8), date(2026, 2, 15))
    # Unknown → default window.
    lo, hi = spontaneity_window("nonsense", today)
    default_lo, default_hi = spontaneity_window(DEFAULT_SPONTANEITY, today)
    assert (lo, hi) == (default_lo, default_hi)
