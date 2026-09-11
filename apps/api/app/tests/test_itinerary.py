import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.billing.usage import get_ai_usage
from app.config import settings
from app.database import get_db
from app.db.models import TripSuggestionDB, UserDB
from app.itinerary import service as itinerary_service
from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
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


def _first_suggestion_id(client, search=None) -> str:
    res = client.post("/trips/search", json=search or SEARCH)
    assert res.status_code == 200
    sid = res.json()["trips"][0]["suggestionId"]
    assert sid
    return sid


def _signup_verified(client, db_session, email="planner@example.com") -> UserDB:
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "Strong-pass-123!",
            "displayName": "Planner",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        },
    )
    assert response.status_code == 200
    user = db_session.scalar(select(UserDB).where(UserDB.email == email))
    assert user
    user.is_verified = True
    db_session.commit()
    return user


def test_plan_requires_ai_enabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    client = make_client(db_session)
    authenticated_search = {**SEARCH, "originAirports": SEARCH["originAirports"][:3]}
    sid = _first_suggestion_id(client, authenticated_search)

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
    authenticated_search = {**SEARCH, "originAirports": SEARCH["originAirports"][:3]}
    sid = _first_suggestion_id(client, authenticated_search)

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


def test_authenticated_plan_uses_one_ai_search_and_cached_reopen_is_free(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(itinerary_service, "build_ai_provider", lambda: FakeProvider())
    client = make_client(db_session)
    user = _signup_verified(client, db_session)
    authenticated_search = {**SEARCH, "originAirports": SEARCH["originAirports"][:3]}
    sid = _first_suggestion_id(client, authenticated_search)

    first = client.post(f"/trips/suggestions/{sid}/plan")
    usage_after_generation = get_ai_usage(db_session, user)
    second = client.post(f"/trips/suggestions/{sid}/plan")
    usage_after_reopen = get_ai_usage(db_session, user)

    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert usage_after_generation == 1
    assert usage_after_reopen == 1
    app.dependency_overrides.clear()


def test_plan_respects_account_ai_limit_before_calling_provider(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "triplet_free_ai_searches_per_month", 0)
    calls = {"n": 0}

    def fake_build():
        calls["n"] += 1
        return FakeProvider()

    monkeypatch.setattr(itinerary_service, "build_ai_provider", fake_build)
    client = make_client(db_session)
    _signup_verified(client, db_session, "limited-planner@example.com")
    authenticated_search = {**SEARCH, "originAirports": SEARCH["originAirports"][:3]}
    sid = _first_suggestion_id(client, authenticated_search)

    response = client.post(f"/trips/suggestions/{sid}/plan")

    assert response.status_code == 402
    assert "AI searches" in response.json()["detail"]
    assert calls["n"] == 0
    app.dependency_overrides.clear()


def test_expired_suggestion_is_not_visible_or_plannable(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    client = make_client(db_session)
    sid = _first_suggestion_id(client)
    row = db_session.get(TripSuggestionDB, sid)
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert client.get(f"/trips/suggestions/{sid}").status_code == 404
    assert client.post(f"/trips/suggestions/{sid}/plan").status_code == 404
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
