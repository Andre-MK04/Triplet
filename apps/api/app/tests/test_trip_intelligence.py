from datetime import date, datetime

from fastapi.testclient import TestClient

from app.database import get_db
from app.db.models import UserTravelProfileDB
from app.main import app
from app.models import Flight, GroundTransfer, TripOption, TripSearchRequest
from app.services.trip_scoring import (
    ScoringContext,
    calculate_deal_score,
    calculate_fit_score,
    route_key,
)


def request(**overrides) -> TripSearchRequest:
    values = {
        "originAirports": ["VIE"],
        "startDate": date(2026, 7, 1),
        "endDate": date(2026, 8, 31),
        "minTripLengthDays": 1,
        "maxTripLengthDays": 12,
        "maxBudget": 200,
        "maxGroundTransferHours": 5,
        "tripStyle": "surprise me",
    }
    values.update(overrides)
    return TripSearchRequest(**values)


def flight(**overrides) -> Flight:
    values = {
        "id": "fl-1",
        "origin": "VIE",
        "destination": "ALC",
        "departureDateTime": datetime(2026, 8, 10, 9, 0),
        "arrivalDateTime": datetime(2026, 8, 10, 12, 0),
        "airline": "Test Air",
        "price": 50.0,
    }
    values.update(overrides)
    return Flight(**values)


def trip(**overrides) -> TripOption:
    values = {
        "id": "trip-1",
        "tripType": "same_city",
        "outboundFlight": flight(),
        "returnFlight": flight(
            id="fl-2",
            origin="ALC",
            destination="VIE",
            departureDateTime=datetime(2026, 8, 16, 14, 0),
            arrivalDateTime=datetime(2026, 8, 16, 17, 0),
        ),
        "groundTransfer": None,
        "totalPrice": 100.0,
        "tripLengthDays": 6,
        "nights": 6,
        "score": 0,
        "explanation": "",
        "warnings": [],
        "tags": [],
    }
    values.update(overrides)
    return TripOption(**values)


def profile(**overrides) -> UserTravelProfileDB:
    values = dict(
        user_id="u-1",
        origin_airports=["VIE", "ZAG"],
        max_airport_travel_time_minutes=120,
        preferred_trip_types=["beach"],
        preferred_trip_length_min=4,
        preferred_trip_length_max=8,
        budget_comfort_zone="under_200",
        spontaneity="next_month",
        comfort_rules=[],
        open_jaw_willingness="nearby_city_open_jaw",
        notification_frequency="weekly_digest",
        excluded_airlines=[],
        preferred_months=[8],
    )
    values.update(overrides)
    return UserTravelProfileDB(**values)


def test_price_history_below_baseline_boosts_deal_score():
    stats = {
        route_key("VIE", "ALC"): {"count": 10, "minPrice": 45.0, "avgPrice": 110.0},
        route_key("ALC", "VIE"): {"count": 10, "minPrice": 48.0, "avgPrice": 105.0},
    }
    without_history, _ = calculate_deal_score(trip(), request())
    with_history, components = calculate_deal_score(trip(), request(), ScoringContext(route_stats=stats))

    assert with_history > without_history
    assert any("typical observed price" in component.label for component in components)


def test_price_history_above_baseline_lowers_deal_score():
    stats = {
        route_key("VIE", "ALC"): {"count": 10, "minPrice": 20.0, "avgPrice": 38.0},
        route_key("ALC", "VIE"): {"count": 10, "minPrice": 20.0, "avgPrice": 38.0},
    }
    baseline, _ = calculate_deal_score(trip(), request())
    overpriced, _ = calculate_deal_score(trip(), request(), ScoringContext(route_stats=stats))

    assert overpriced < baseline


def test_thin_price_history_is_ignored():
    stats = {route_key("VIE", "ALC"): {"count": 1, "minPrice": 45.0, "avgPrice": 200.0}}
    without_history, _ = calculate_deal_score(trip(), request())
    with_thin_history, _ = calculate_deal_score(trip(), request(), ScoringContext(route_stats=stats))

    assert with_thin_history == without_history


def test_fit_score_rewards_profile_match():
    matching, components = calculate_fit_score(trip(), request(), profile())

    labels = " ".join(component.label for component in components)
    assert matching > 70
    assert "your airports" in labels
    assert "preferred trip length" in labels
    assert "preferred months" in labels


def test_fit_score_penalizes_comfort_rule_violations():
    strict = profile(comfort_rules=["direct_only", "no_departures_before_6am"])
    bad_trip = trip(
        outboundFlight=flight(stops=1, departureDateTime=datetime(2026, 8, 10, 5, 0)),
        returnFlight=flight(id="fl-2", origin="ALC", destination="VIE", stops=0,
                            departureDateTime=datetime(2026, 8, 16, 14, 0),
                            arrivalDateTime=datetime(2026, 8, 16, 17, 0)),
    )
    relaxed_score, _ = calculate_fit_score(bad_trip, request(), profile())
    strict_score, components = calculate_fit_score(bad_trip, request(), strict)

    assert strict_score < relaxed_score
    assert any("direct-only" in component.label for component in components)


def test_fit_score_open_jaw_respects_willingness():
    transfer = GroundTransfer(
        fromAirport="ALC", toAirport="VLC", fromCity="Alicante", toCity="Valencia",
        durationHours=2, estimatedCost=20, mode="train/bus",
    )
    open_jaw = trip(tripType="open_jaw", groundTransfer=transfer)

    simple_only, _ = calculate_fit_score(open_jaw, request(), profile(open_jaw_willingness="simple_returns_only"))
    adventurous, _ = calculate_fit_score(open_jaw, request(), profile(open_jaw_willingness="adventurous_multi_city"))

    assert simple_only < adventurous


def test_fit_score_without_profile_uses_request_only():
    score, _ = calculate_fit_score(trip(), request())

    assert 0 <= score <= 100


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def search_payload():
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


def test_search_persists_suggestions_and_detail_endpoint_serves_them(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    search = client.post("/trips/search", json=search_payload())
    assert search.status_code == 200
    trips = search.json()["trips"]
    assert trips
    assert trips[0]["dealScore"] > 0
    assert trips[0]["suggestionId"]
    assert isinstance(trips[0]["dealScoreBreakdown"], list)

    detail = client.get(f"/trips/suggestions/{trips[0]['suggestionId']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["trip"]["id"] == trips[0]["id"]
    assert body["dealScore"] == trips[0]["dealScore"]
    assert "disclaimer" in body

    app.dependency_overrides.clear()


def test_unknown_suggestion_returns_404(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    response = client.get("/trips/suggestions/does-not-exist")

    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_user_owned_suggestions_are_private(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    signup = client.post(
        "/auth/signup",
        json={"email": "intel-tester@example.com", "password": "Strong-pass-123!", "displayName": "T"},
    )
    assert signup.status_code == 200

    search = client.post("/trips/search", json=search_payload())
    suggestion_id = search.json()["trips"][0]["suggestionId"]
    assert suggestion_id

    # Owner can read it; a logged-out client cannot.
    assert client.get(f"/trips/suggestions/{suggestion_id}").status_code == 200
    client.post("/auth/logout")
    assert client.get(f"/trips/suggestions/{suggestion_id}").status_code == 404

    app.dependency_overrides.clear()
