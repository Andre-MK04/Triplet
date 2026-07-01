from datetime import date

import pytest

from app.tools.base import ToolContext
from app.tools.registry import ToolNotFoundError, ToolValidationError, build_default_tool_registry


def search_input():
    return {
        "originAirports": ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"],
        "startDate": "2026-07-01",
        "endDate": "2026-08-31",
        "minTripLengthDays": 4,
        "maxTripLengthDays": 8,
        "maxBudget": 180,
        "maxGroundTransferHours": 4,
        "tripStyle": "surprise me",
    }


def test_tool_registry_lists_tools():
    registry = build_default_tool_registry()

    names = {tool["name"] for tool in registry.list_tools()}

    assert {"search_trips", "get_airports", "estimate_ground_transfer", "explain_trip", "parse_trip_intent"}.issubset(names)


def test_tool_registry_rejects_unknown_tool_names(db_session):
    registry = build_default_tool_registry()

    with pytest.raises(ToolNotFoundError):
        registry.run_tool("missing_tool", {}, ToolContext(db=db_session))


def test_tool_registry_validates_input(db_session):
    registry = build_default_tool_registry()

    with pytest.raises(ToolValidationError) as exc:
        registry.run_tool("search_trips", {"originAirports": []}, ToolContext(db=db_session))

    assert exc.value.errors


def test_search_trips_tool_returns_trips(db_session):
    registry = build_default_tool_registry()

    result = registry.run_tool("search_trips", search_input(), ToolContext(db=db_session))

    assert result.trips
    assert any(trip.tripType == "open_jaw" for trip in result.trips)


def test_get_airports_tool_returns_airports(db_session):
    registry = build_default_tool_registry()

    result = registry.run_tool("get_airports", {"originCandidatesOnly": True}, ToolContext(db=db_session))

    assert {airport.code for airport in result.airports} == {"LJU", "ZAG", "VIE", "GRZ", "BUD", "TRS", "VCE", "TSF"}


def test_estimate_ground_transfer_returns_known_transfer(db_session):
    registry = build_default_tool_registry()

    result = registry.run_tool(
        "estimate_ground_transfer",
        {"fromAirport": "ALC", "toAirport": "VLC"},
        ToolContext(db=db_session),
    )

    assert result.exists is True
    assert result.transfer.durationHours == 2.0


def test_estimate_ground_transfer_returns_false_for_unknown_transfer(db_session):
    registry = build_default_tool_registry()

    result = registry.run_tool(
        "estimate_ground_transfer",
        {"fromAirport": "ATH", "toAirport": "OPO"},
        ToolContext(db=db_session),
    )

    assert result.exists is False
    assert result.transfer is None


def test_explain_trip_tool_returns_explanation_warnings_tags(db_session):
    registry = build_default_tool_registry()
    trips = registry.run_tool("search_trips", search_input(), ToolContext(db=db_session)).trips

    result = registry.run_tool(
        "explain_trip",
        {"trip": trips[0].model_dump(mode="json")},
        ToolContext(db=db_session),
    )

    assert result.explanation
    assert result.warnings
    assert result.tags
