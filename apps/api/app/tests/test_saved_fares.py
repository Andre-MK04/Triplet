from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.dependencies import get_current_user_required
from app.database import get_db
from app.db.models import SavedFareDB, TripSuggestionDB, UserDB
from app.main import app


def _client(db_session, user):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_required] = lambda: user
    return TestClient(app)


def _suggestion(db_session, user_id="fare-owner", suggestion_id="suggestion-1"):
    row = TripSuggestionDB(
        id=suggestion_id, user_id=user_id, title="Vienna → Stockholm return",
        trip_type="multi_city", origin_airport="VIE", outbound_destination="STO",
        final_arrival_airport="VIE", start_date=date(2026, 10, 1), end_date=date(2026, 10, 8),
        nights=7, total_price=245, currency="EUR", deal_score=70,
        payload={"bookingUrl": "https://www.aviasales.com/search/VIESTO",
                 "outboundFlight": {"observedAt": "2026-09-15T12:00:00Z"}},
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_saved_fare_is_observed_snapshot_idempotent_and_private(db_session):
    owner = UserDB(id="fare-owner", email="fare-owner@example.test", password_hash="unused", is_verified=True)
    other = UserDB(id="fare-other", email="fare-other@example.test", password_hash="unused", is_verified=True)
    db_session.add_all([owner, other])
    db_session.commit()
    _suggestion(db_session)
    client = _client(db_session, owner)
    first = client.post("/me/saved-fares/suggestion-1")
    assert first.status_code == 200
    assert first.json()["observedPrice"] == 245
    assert first.json()["fareStatus"] == "indicative"
    assert "not a reserved or monitored price" in first.json()["disclaimer"]
    assert "each flight separately" in first.json()["disclaimer"]
    assert first.json()["checkPriceUrl"] is None
    assert client.post("/me/saved-fares/suggestion-1").json()["id"] == first.json()["id"]
    assert len(client.get("/me/saved-fares").json()) == 1
    assert len(db_session.scalars(select(SavedFareDB)).all()) == 1

    app.dependency_overrides[get_current_user_required] = lambda: other
    assert client.get("/me/saved-fares").json() == []
    assert client.delete(f"/me/saved-fares/{first.json()['id']}").status_code == 404
    assert client.post("/me/saved-fares/suggestion-1").status_code == 404
    app.dependency_overrides.clear()


def test_saved_fare_delete_and_expired_suggestion(db_session):
    owner = UserDB(id="fare-owner", email="fare-owner@example.test", password_hash="unused", is_verified=True)
    db_session.add(owner)
    db_session.commit()
    suggestion = _suggestion(db_session)
    client = _client(db_session, owner)
    saved_id = client.post("/me/saved-fares/suggestion-1").json()["id"]
    assert client.delete(f"/me/saved-fares/{saved_id}").json() == {"deleted": True}
    assert client.get("/me/saved-fares").json() == []
    suggestion.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    assert client.post("/me/saved-fares/suggestion-1").status_code == 404
    app.dependency_overrides.clear()


def test_saved_fares_require_authentication():
    client = TestClient(app)
    assert client.get("/me/saved-fares").status_code == 401
    assert client.post("/me/saved-fares/suggestion-1").status_code == 401


def test_mock_offer_saved_as_demo_not_live(db_session):
    user = UserDB(id="fare-owner", email="fare-owner@example.test", password_hash="unused", is_verified=True)
    db_session.add(user)
    db_session.commit()
    suggestion = _suggestion(db_session)
    suggestion.payload = {
        "outboundFlight": {"confidenceLevel": "mock", "observedAt": "2026-09-15T12:00:00Z"},
        "price": {"isLive": False, "isEstimate": False},
    }
    db_session.commit()
    client = _client(db_session, user)
    assert client.post("/me/saved-fares/suggestion-1").json()["fareStatus"] == "demo"
    app.dependency_overrides.clear()


def test_unsafe_provider_link_is_not_saved(db_session):
    user = UserDB(id="fare-owner", email="fare-owner@example.test", password_hash="unused", is_verified=True)
    db_session.add(user)
    db_session.commit()
    suggestion = _suggestion(db_session)
    suggestion.payload = {"bookingUrl": "javascript:alert(1)",
                          "outboundFlight": {"bookingUrl": "https://user:pass@example.com/search"}}
    db_session.commit()
    client = _client(db_session, user)
    assert client.post("/me/saved-fares/suggestion-1").json()["checkPriceUrl"] is None
    app.dependency_overrides.clear()


def test_saved_itinerary_keeps_every_segment_after_suggestion_expiry(db_session):
    from app.tests.test_itinerary_builder import request, spread
    from app.services.itinerary_builder import build_itineraries, plan_route

    owner = UserDB(id="fare-owner", email="fare-owner@example.test", password_hash="unused", is_verified=True)
    db_session.add(owner)
    db_session.commit()
    suggestion = _suggestion(db_session)
    ask = request(originAirports=["CPH"], routeStops=["ATH", "SKP", "BEG", "SOF"])
    fares = {pair: spread(*pair, price) for pair, price in [
        (("CPH", "ATH"), 110), (("ATH", "SKP"), 70), (("SOF", "CPH"), 59)]}
    trip = build_itineraries(ask, "CPH", plan_route(ask, "CPH"), fares)[0]
    suggestion.payload = trip.model_dump(mode="json")
    db_session.commit()
    client = _client(db_session, owner)
    result = client.post("/me/saved-fares/suggestion-1")
    assert result.status_code == 200
    assert len(result.json()["trip"]["segments"]) == 5
    assert result.json()["trip"]["segments"][2]["kind"] == "ground"
    suggestion.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    restored = client.get("/me/saved-fares").json()[0]["trip"]
    assert restored["segments"] == result.json()["trip"]["segments"]
    assert restored["suggestionId"] == "suggestion-1"
    app.dependency_overrides.clear()
