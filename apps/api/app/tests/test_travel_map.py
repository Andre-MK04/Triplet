from fastapi.testclient import TestClient

from app.data.country_catalog import country_catalog, get_country, search_countries
from app.ai.orchestrator import build_travel_map_context, build_user_message
from app.ai.schemas import AISearchRequest
from app.database import get_db
from app.main import app
from app.tools.base import ToolContext
from app.travel_map.service import TravelMapService, format_partial_date, parse_partial_date
from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION


def make_client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def signup(client, email="map@example.com"):
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "Strong-pass-123!", "displayName": "Map Tester",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        },
    )
    assert response.status_code == 200
    return response


def test_country_catalog_is_centralized_and_searchable():
    catalog = country_catalog()
    assert catalog.world_total == 195
    assert catalog.continents == (
        "Africa", "Antarctica", "Asia", "Europe", "North America", "South America", "Oceania"
    )
    assert get_country("is").name == "Iceland"
    assert get_country("TR").continent == "Asia"
    assert search_countries("czech republic")[0].code == "CZ"
    assert search_countries("KOR")[0].code == "KR"


def test_country_catalog_endpoint_is_public(db_session):
    client = make_client(db_session)
    response = client.get("/countries?q=ice")
    assert response.status_code == 200
    assert response.json()["worldTotal"] == 195
    assert response.json()["countries"][0]["code"] == "IS"
    app.dependency_overrides.clear()


def test_travel_map_requires_authentication(db_session):
    client = make_client(db_session)
    assert client.get("/me/travel-map").status_code == 401
    assert client.patch("/me/travel-map/countries/IS", json={"visited": True}).status_code == 401
    assert client.post("/me/travel-map/countries/IS/visits", json={}).status_code == 401
    app.dependency_overrides.clear()


def test_country_status_precedence_and_persistence(db_session):
    client = make_client(db_session)
    signup(client)

    wishlist = client.patch("/me/travel-map/countries/IS", json={"wishlist": True})
    assert wishlist.status_code == 200
    assert wishlist.json()["primaryStatus"] == "wishlist"

    visited = client.patch("/me/travel-map/countries/IS", json={"visited": True})
    assert visited.json()["visited"] is True
    assert visited.json()["wishlist"] is False
    assert visited.json()["primaryStatus"] == "visited"

    lived = client.patch("/me/travel-map/countries/IS", json={"lived": True})
    assert lived.json()["lived"] is True
    assert lived.json()["visited"] is True
    assert lived.json()["primaryStatus"] == "lived"

    refreshed = client.get("/me/travel-map").json()
    assert refreshed["countries"][0]["code"] == "IS"
    assert refreshed["countries"][0]["primaryStatus"] == "lived"
    assert refreshed["stats"]["countriesVisited"] == 1
    assert refreshed["stats"]["countriesLivedIn"] == 1
    assert refreshed["stats"]["continentsVisited"] == 1
    assert refreshed["stats"]["worldTotal"] == 195
    assert refreshed["stats"]["worldExploredPercentage"] == 0.5
    app.dependency_overrides.clear()


def test_bulk_add_supports_fast_country_entry(db_session):
    client = make_client(db_session)
    signup(client)
    response = client.post(
        "/me/travel-map/countries/bulk",
        json={"countryCodes": ["AT", "BE", "HR"], "status": "visited"},
    )
    assert response.status_code == 200
    assert response.json()["stats"]["countriesVisited"] == 3
    assert {country["code"] for country in response.json()["countries"]} == {"AT", "BE", "HR"}
    app.dependency_overrides.clear()


def test_multiple_visits_and_partial_dates_round_trip(db_session):
    client = make_client(db_session)
    signup(client)
    first = client.post(
        "/me/travel-map/countries/IT/visits",
        json={"startDate": "2023-05", "endDate": "2023-05", "note": "Rome"},
    )
    second = client.post(
        "/me/travel-map/countries/IT/visits",
        json={"startDate": "2024", "kind": "visit"},
    )
    third = client.post(
        "/me/travel-map/countries/IT/visits",
        json={"startDate": "2026-03-04", "endDate": "2026-03-12"},
    )
    assert [first.status_code, second.status_code, third.status_code] == [201, 201, 201]
    assert first.json()["startPrecision"] == "month"
    assert second.json()["startPrecision"] == "year"
    assert third.json()["startPrecision"] == "exact"

    country = client.get("/me/travel-map").json()["countries"][0]
    assert country["visitCount"] == 3
    assert [visit["startDate"] for visit in country["visits"]] == ["2026-03-04", "2024", "2023-05"]

    duplicate = client.post(
        "/me/travel-map/countries/IT/visits",
        json={"startDate": "2024", "kind": "visit"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "That visit is already recorded."
    app.dependency_overrides.clear()


def test_visit_edit_delete_and_status_safety(db_session):
    client = make_client(db_session)
    signup(client)
    created = client.post(
        "/me/travel-map/countries/ES/visits",
        json={"kind": "lived", "startDate": "2026-02", "endDate": "2026-06"},
    ).json()

    blocked = client.patch("/me/travel-map/countries/ES", json={"lived": False})
    assert blocked.status_code == 409

    edited = client.patch(
        f"/me/travel-map/visits/{created['id']}",
        json={"kind": "lived", "startDate": "2026-01", "endDate": "2026-06", "note": "Study"},
    )
    assert edited.status_code == 200
    assert edited.json()["startDate"] == "2026-01"

    deleted = client.delete(f"/me/travel-map/visits/{created['id']}")
    assert deleted.status_code == 200
    country = client.get("/me/travel-map").json()["countries"][0]
    assert country["residenceCount"] == 0
    assert country["lived"] is True  # durable fact is not silently erased

    cleared = client.patch("/me/travel-map/countries/ES", json={"lived": False})
    assert cleared.status_code == 200
    assert cleared.json()["primaryStatus"] == "visited"
    app.dependency_overrides.clear()


def test_invalid_dates_unknown_countries_and_foreign_visits_are_rejected(db_session):
    client = make_client(db_session)
    signup(client, "owner@example.com")
    assert client.patch("/me/travel-map/countries/XX", json={"visited": True}).status_code == 400
    assert client.post(
        "/me/travel-map/countries/FR/visits", json={"startDate": "2026-13"}
    ).status_code == 400
    visit_id = client.post(
        "/me/travel-map/countries/FR/visits", json={"startDate": "2025-04"}
    ).json()["id"]
    client.post("/auth/logout")
    signup(client, "other@example.com")
    assert client.patch(
        f"/me/travel-map/visits/{visit_id}", json={"startDate": "2025-05"}
    ).status_code == 404
    assert client.delete(f"/me/travel-map/visits/{visit_id}").status_code == 404
    app.dependency_overrides.clear()


def test_ai_context_is_compact_country_codes_only(db_session):
    client = make_client(db_session)
    signup(client)
    client.patch("/me/travel-map/countries/SE", json={"visited": True})
    client.patch("/me/travel-map/countries/SI", json={"lived": True})
    client.patch("/me/travel-map/countries/JP", json={"wishlist": True})

    from app.db.models import UserDB
    from sqlalchemy import select

    user = db_session.scalar(select(UserDB).where(UserDB.email == "map@example.com"))
    context = TravelMapService(db_session, user).compact_ai_context()
    assert context == {
        "visitedCountries": ["SE", "SI"],
        "livedCountries": ["SI"],
        "wishlistCountries": ["JP"],
    }
    assert "note" not in str(context).lower()
    app.dependency_overrides.clear()


def test_ai_context_is_selective_and_never_contains_visit_notes(db_session):
    client = make_client(db_session)
    signup(client)
    client.post(
        "/me/travel-map/countries/IT/visits",
        json={"startDate": "2024-08", "note": "Private family memory"},
    )
    client.patch("/me/travel-map/countries/JP", json={"wishlist": True})

    from app.db.models import UserDB
    from sqlalchemy import select

    user = db_session.scalar(select(UserDB).where(UserDB.email == "map@example.com"))
    context = ToolContext(db=db_session, user_id=user.id)
    assert build_travel_map_context("Find somewhere warm in August", context) is None

    compact = build_travel_map_context("Find somewhere new that I have never visited", context)
    assert compact == {
        "visitedCountries": ["IT"],
        "livedCountries": [],
        "wishlistCountries": ["JP"],
    }
    prompt = build_user_message(
        AISearchRequest(message="Find somewhere new that I have never visited"),
        compact,
    )
    assert "Private family memory" not in prompt
    assert "2024-08" not in prompt
    assert "'IT'" in prompt
    assert build_travel_map_context("I want to visit a new continent", context) == compact
    assert build_travel_map_context("Don't recommend countries I've already visited", context) == compact
    app.dependency_overrides.clear()


def test_partial_date_helpers():
    assert format_partial_date(*parse_partial_date("2024")) == "2024"
    assert format_partial_date(*parse_partial_date("2024-08")) == "2024-08"
    assert format_partial_date(*parse_partial_date("2024-08-19")) == "2024-08-19"
    assert parse_partial_date(None) == (None, "unknown")
