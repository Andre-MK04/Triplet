from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def make_client(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    return TestClient(app)


def signup(client, email="profile-tester@example.com"):
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "Strong-pass-123!", "displayName": "Profile Tester"},
    )
    assert response.status_code == 200
    return response


def profile_payload(**overrides):
    payload = {
        "homeLocation": "Ljubljana, Slovenia",
        "originAirports": ["vie", "zag", "trs"],
        "maxAirportTravelTimeMinutes": 150,
        "preferredTripTypes": ["food", "beach", "weekend_city_break"],
        "preferredTripLengthMin": 4,
        "preferredTripLengthMax": 8,
        "budgetComfortZone": "under_200",
        "spontaneity": "next_month",
        "comfortRules": ["max_one_stop", "no_departures_before_6am"],
        "openJawWillingness": "nearby_city_open_jaw",
        "notificationFrequency": "weekly_digest",
        "excludedAirlines": [],
        "preferredMonths": [7, 8, 9],
    }
    payload.update(overrides)
    return payload


def test_travel_profile_requires_login(db_session):
    client = make_client(db_session)

    assert client.get("/me/travel-profile").status_code == 401
    assert client.put("/me/travel-profile", json=profile_payload()).status_code == 401

    app.dependency_overrides.clear()


def test_travel_profile_defaults_before_onboarding(db_session):
    client = make_client(db_session)
    signup(client)

    response = client.get("/me/travel-profile")

    assert response.status_code == 200
    body = response.json()
    assert body["isComplete"] is False
    assert body["originAirports"]

    app.dependency_overrides.clear()


def test_travel_profile_upsert_roundtrip_normalizes_codes(db_session):
    client = make_client(db_session)
    signup(client)

    put_response = client.put("/me/travel-profile", json=profile_payload())
    assert put_response.status_code == 200
    saved = put_response.json()
    assert saved["isComplete"] is True
    assert saved["originAirports"] == ["VIE", "ZAG", "TRS"]
    assert saved["preferredMonths"] == [7, 8, 9]

    get_response = client.get("/me/travel-profile")
    assert get_response.status_code == 200
    assert get_response.json()["homeLocation"] == "Ljubljana, Slovenia"

    update = client.put("/me/travel-profile", json=profile_payload(budgetComfortZone="under_400"))
    assert update.status_code == 200
    assert update.json()["budgetComfortZone"] == "under_400"

    app.dependency_overrides.clear()


def test_travel_profile_rejects_invalid_values(db_session):
    client = make_client(db_session)
    signup(client)

    bad_airport = client.put("/me/travel-profile", json=profile_payload(originAirports=["VIENNA1"]))
    assert bad_airport.status_code == 422

    bad_range = client.put(
        "/me/travel-profile",
        json=profile_payload(preferredTripLengthMin=9, preferredTripLengthMax=3),
    )
    assert bad_range.status_code == 422

    bad_month = client.put("/me/travel-profile", json=profile_payload(preferredMonths=[13]))
    assert bad_month.status_code == 422

    app.dependency_overrides.clear()


def test_travel_profile_respects_origin_airport_plan_limit(db_session):
    client = make_client(db_session)
    signup(client)

    too_many = client.put(
        "/me/travel-profile",
        json=profile_payload(originAirports=["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU", "MUC"]),
    )

    assert too_many.status_code == 402  # free plan allows up to 6 origin airports

    app.dependency_overrides.clear()


def test_travel_profiles_are_per_user(db_session):
    client = make_client(db_session)
    signup(client, email="user-a@example.com")
    client.put("/me/travel-profile", json=profile_payload(homeLocation="Vienna"))
    client.post("/auth/logout")

    signup(client, email="user-b@example.com")
    response = client.get("/me/travel-profile")

    assert response.status_code == 200
    assert response.json()["isComplete"] is False
    assert response.json()["homeLocation"] != "Vienna"

    app.dependency_overrides.clear()
