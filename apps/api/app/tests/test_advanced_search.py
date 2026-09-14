from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.dependencies import get_current_user_required
from app.database import get_db
from app.db.models import UsageCounterDB, UserDB, UserTravelProfileDB
from app.main import app


def _override_db(db_session):
    def override():
        yield db_session

    return override


def _user_with_profile(db_session) -> UserDB:
    user = UserDB(
        id="advanced-search-user",
        email="advanced@example.test",
        password_hash="not-used",
        is_verified=True,
    )
    profile = UserTravelProfileDB(
        user_id=user.id,
        origin_airports=["VIE", "ZAG"],
        preferred_trip_types=["food", "culture"],
        preferred_trip_length_min=4,
        preferred_trip_length_max=8,
        spontaneity="planner",
        comfort_rule_modes={"direct_only": "require"},
        comfort_rules=["direct_only"],
        deal_sensitivity="balanced",
    )
    db_session.add_all([user, profile])
    db_session.commit()
    return user


def test_advanced_search_resolves_profile_and_explicit_overrides(db_session):
    user = _user_with_profile(db_session)
    app.dependency_overrides[get_db] = _override_db(db_session)
    app.dependency_overrides[get_current_user_required] = lambda: user
    client = TestClient(app)

    response = client.post(
        "/trips/advanced-search",
        json={
            "destinationAirports": ["ALC"],
            "startDate": "2026-07-01",
            "endDate": "2026-07-31",
            "maxBudget": 220,
            "directOnly": False,
            "travelStyles": ["beach"],
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["parsedRequest"]["originAirports"] == ["VIE", "ZAG"]
    assert body["parsedRequest"]["destinationAirports"] == ["ALC"]
    assert body["parsedRequest"]["maxBudget"] == 220
    assert body["parsedRequest"]["directOnly"] is False
    assert body["parsedRequest"]["travelStyles"] == ["beach"]
    assert body["sourceMap"]["originAirports"] == "profile"
    assert body["sourceMap"]["dateRange"] == "search"
    assert body["sourceMap"]["directOnly"] == "search"
    assert body["sourceMap"]["travelStyles"] == "search"
    assert body["hardBudgetApplied"] is True
    assert db_session.scalars(select(UsageCounterDB).where(UsageCounterDB.user_id == user.id)).all() == []


def test_advanced_search_without_budget_uses_broad_internal_ceiling(db_session):
    user = _user_with_profile(db_session)
    app.dependency_overrides[get_db] = _override_db(db_session)
    app.dependency_overrides[get_current_user_required] = lambda: user
    client = TestClient(app)

    response = client.post(
        "/trips/advanced-search",
        json={
            "startDate": "2026-07-01",
            "endDate": "2026-08-31",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["hardBudgetApplied"] is False
    assert response.json()["sourceMap"]["maxBudget"] == "default"


def test_advanced_search_requires_authentication():
    client = TestClient(app)

    response = client.post("/trips/advanced-search", json={})

    assert response.status_code == 401


def test_advanced_multi_city_requires_ordered_stops(db_session):
    user = _user_with_profile(db_session)
    app.dependency_overrides[get_db] = _override_db(db_session)
    app.dependency_overrides[get_current_user_required] = lambda: user
    client = TestClient(app)

    response = client.post(
        "/trips/advanced-search",
        json={
            "tripPlan": "multi_city",
            "startDate": "2026-07-01",
            "endDate": "2026-08-31",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "at least two destinations" in response.json()["detail"]


def test_advanced_open_jaw_preserves_arrival_and_fly_home_airports(db_session):
    user = _user_with_profile(db_session)
    app.dependency_overrides[get_db] = _override_db(db_session)
    app.dependency_overrides[get_current_user_required] = lambda: user
    client = TestClient(app)

    response = client.post(
        "/trips/advanced-search",
        json={
            "tripPlan": "open_jaw",
            "destinationAirports": ["STO"],
            "returnOriginAirports": ["HEL"],
            "startDate": "2026-07-01",
            "endDate": "2026-08-31",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["parsedRequest"]["tripPlan"] == "open_jaw"
    assert response.json()["parsedRequest"]["destinationAirports"] == ["STO"]
    assert response.json()["parsedRequest"]["returnOriginAirports"] == ["HEL"]
