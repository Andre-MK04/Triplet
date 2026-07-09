import json

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.itinerary import service as itinerary_service
from app.main import app


def override_db(db_session):
    def _override():
        yield db_session

    return _override


def make_client(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    return TestClient(app)


SEARCH = {
    "originAirports": ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"],
    "startDate": "2026-07-01", "endDate": "2026-08-31",
    "minTripLengthDays": 4, "maxTripLengthDays": 8, "maxBudget": 180,
    "maxGroundTransferHours": 4, "tripStyle": "surprise me",
}

CANNED_PLAN = {
    "summary": "Three days of food and old-town wandering.",
    "days": [
        {"label": "Day 1 — arrival", "items": [
            {"partOfDay": "evening", "title": "Dinner in the old town",
             "description": "Try the local grilled fish.", "category": "food", "estimatedCost": "€20–35"}
        ]},
    ],
    "gettingAround": "Walkable centre; buses to the airport ~€3.",
    "extraCostEstimate": "€60–120 over the trip",
    "disclaimers": [],
}


class FakeProvider:
    def complete_json(self, system, user):
        return json.dumps(CANNED_PLAN)


def _first_suggestion_id(client) -> str:
    res = client.post("/trips/search", json=SEARCH)
    assert res.status_code == 200
    sid = res.json()["trips"][0]["suggestionId"]
    assert sid
    return sid


def test_plan_requires_ai_enabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    client = make_client(db_session)
    sid = _first_suggestion_id(client)

    res = client.post(f"/trips/suggestions/{sid}/plan")
    assert res.status_code == 503

    app.dependency_overrides.clear()


def test_plan_generates_then_caches(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    calls = {"n": 0}

    def fake_build():
        calls["n"] += 1
        return FakeProvider()

    monkeypatch.setattr(itinerary_service, "build_ai_provider", fake_build)
    client = make_client(db_session)
    sid = _first_suggestion_id(client)

    first = client.post(f"/trips/suggestions/{sid}/plan")
    assert first.status_code == 200
    body = first.json()
    assert body["cached"] is False
    assert body["itinerary"]["summary"].startswith("Three days")
    # Standing verification disclaimer is always appended.
    assert any("confirm" in d.lower() for d in body["itinerary"]["disclaimers"])

    second = client.post(f"/trips/suggestions/{sid}/plan")
    assert second.status_code == 200
    assert second.json()["cached"] is True
    # Cached: the model was only invoked once.
    assert calls["n"] == 1

    app.dependency_overrides.clear()


def test_plan_unknown_suggestion_404(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    client = make_client(db_session)
    res = client.post("/trips/suggestions/does-not-exist/plan")
    assert res.status_code == 404
    app.dependency_overrides.clear()


def test_itinerary_prompt_includes_constraints_and_interests():
    trip = {
        "tripType": "same_city",
        "nights": 4,
        "outboundFlight": {"origin": "VIE", "destination": "CPH", "currency": "EUR",
                           "arrivalDateTime": "2026-08-05T12:00:00"},
        "returnFlight": {"origin": "CPH", "destination": "VIE",
                         "departureDateTime": "2026-08-09T18:00:00"},
    }
    system, user = itinerary_service._build_prompts(trip, {"preferredTripTypes": ["food"]})
    assert "arrival" in system.lower() and "estimate" in system.lower()
    assert "Copenhagen" in user  # destination city resolved from geography
    assert "Food" in user  # interest label passed through
