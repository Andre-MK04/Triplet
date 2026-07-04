from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app
from app.routers import airports as airports_router
from app.services import flight_search_service
from app.tools import travel_tools


def test_trip_search_route_works_with_database_provider(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.post(
        "/trips/search",
        json={
            "originAirports": ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"],
            "startDate": "2026-07-01",
            "endDate": "2026-08-31",
            "minTripLengthDays": 4,
            "maxTripLengthDays": 8,
            "maxBudget": 180,
            "maxGroundTransferHours": 4,
            "tripStyle": "surprise me",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    trips = response.json()["trips"]
    assert trips
    assert {"score", "explanation", "warnings", "tags"}.issubset(trips[0].keys())
    assert any(trip["tripType"] == "same_city" for trip in trips)
    assert any(trip["tripType"] == "open_jaw" for trip in trips)


def test_trip_search_route_returns_clean_error_for_skyscanner_without_api_key(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    monkeypatch.setattr(flight_search_service.settings, "flight_provider", "skyscanner")
    monkeypatch.setattr(flight_search_service.settings, "skyscanner_api_enabled", True)
    monkeypatch.setattr(flight_search_service.settings, "skyscanner_api_key", None)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.post(
        "/trips/search",
        json={
            "originAirports": ["VIE"],
            "startDate": "2026-07-01",
            "endDate": "2026-08-31",
            "minTripLengthDays": 4,
            "maxTripLengthDays": 8,
            "maxBudget": 180,
            "maxGroundTransferHours": 4,
            "tripStyle": "surprise me",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert "Skyscanner API key is missing" in response.json()["detail"]


def test_trip_search_route_returns_503_when_database_is_not_ready(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    def raise_operational_error(self):
        raise OperationalError("select 1", {}, Exception('role "triplet" does not exist'))

    monkeypatch.setattr(travel_tools.AirportsRepository, "list_airports", raise_operational_error)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.post(
        "/trips/search",
        json={
            "originAirports": ["VIE"],
            "startDate": "2026-07-01",
            "endDate": "2026-08-31",
            "minTripLengthDays": 4,
            "maxTripLengthDays": 8,
            "maxBudget": 180,
            "maxGroundTransferHours": 4,
            "tripStyle": "surprise me",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "Database is not ready" in response.json()["detail"]


def test_airports_route_returns_503_when_database_is_not_ready(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    def raise_operational_error(self):
        raise OperationalError("select 1", {}, Exception('role "triplet" does not exist'))

    monkeypatch.setattr(airports_router.AirportsRepository, "list_airports", raise_operational_error)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/airports")
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "Database is not ready" in response.json()["detail"]


def test_trip_search_route_works_in_hybrid_mode_with_mocked_live_provider(db_session, monkeypatch):
    from app.providers.mock_flight_provider import MockFlightProvider

    def override_get_db():
        yield db_session

    monkeypatch.setattr(flight_search_service.settings, "flight_provider", "hybrid")
    monkeypatch.setattr(
        "app.services.flight_search_service.build_live_provider",
        lambda db=None: MockFlightProvider([]),
    )
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.post(
        "/trips/search",
        json={
            "originAirports": ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"],
            "startDate": "2026-07-01",
            "endDate": "2026-08-31",
            "minTripLengthDays": 4,
            "maxTripLengthDays": 8,
            "maxBudget": 180,
            "maxGroundTransferHours": 4,
            "tripStyle": "surprise me",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["trips"]
    assert data["providerUsed"] == "hybrid"
    assert data["providerMetadata"]["liveProviderAttempted"] is True
    assert data["providerMetadata"]["cachedResultsUsed"] is True
