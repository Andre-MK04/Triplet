from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user_required
from app.database import get_db
from app.db.models import CachedRoundTripDB, UserDB, UserTravelProfileDB
from app.main import app


def _client(db_session, user):
    def use_db():
        yield db_session

    app.dependency_overrides[get_db] = use_db
    app.dependency_overrides[get_current_user_required] = lambda: user
    return TestClient(app)


def test_private_opportunity_feed_uses_only_profile_airports_and_provider_sighting(db_session):
    today = date.today()
    now = datetime.utcnow()
    user = UserDB(id="feed-user", email="feed@example.test", password_hash="unused", is_verified=True)
    profile = UserTravelProfileDB(user_id=user.id, origin_airports=["VIE"], budget_comfort_zone="under_200")
    db_session.add_all([
        user,
        profile,
        CachedRoundTripDB(
            origin_code="VIE", destination_code="DUB",
            departure_date=today + timedelta(days=21), return_date=today + timedelta(days=28),
            price=123, currency="EUR", observed_at=now,
            price_seen_at=now - timedelta(days=2),
        ),
        CachedRoundTripDB(
            origin_code="LHR", destination_code="DUB",
            departure_date=today + timedelta(days=21), return_date=today + timedelta(days=28),
            price=50, currency="EUR", observed_at=now, price_seen_at=now,
        ),
        CachedRoundTripDB(
            origin_code="VIE", destination_code="ALC",
            departure_date=today - timedelta(days=3), return_date=today + timedelta(days=4),
            price=30, currency="EUR", observed_at=now, price_seen_at=now,
        ),
    ])
    db_session.commit()

    client = _client(db_session, user)
    try:
        response = client.get("/me/opportunities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    assert body["originAirports"] == ["VIE"]
    assert body["source"] == "cached_database"
    assert body["isReady"] is True
    assert body["isStale"] is True
    assert len(body["trips"]) == 1
    assert body["trips"][0]["outboundFlight"]["origin"] == "VIE"
    assert body["trips"][0]["totalPrice"] == 123
    assert body["trips"][0]["price"]["observedAt"][:10] == (now - timedelta(days=2)).date().isoformat()
    assert body["trips"][0]["outboundFlight"]["isLive"] is False


def test_opportunity_feed_does_not_borrow_sample_origins_for_empty_profile(db_session):
    user = UserDB(id="empty-feed-user", email="empty@example.test", password_hash="unused", is_verified=True)
    db_session.add(user)
    db_session.commit()
    client = _client(db_session, user)
    try:
        response = client.get("/me/opportunities")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["originAirports"] == []
    assert response.json()["trips"] == []
    assert response.json()["isReady"] is False


def test_opportunity_feed_requires_authentication():
    response = TestClient(app).get("/me/opportunities")
    assert response.status_code == 401


def test_flexible_profile_does_not_invent_a_budget_ceiling(db_session):
    from app.deals.opportunities import build_opportunity_feed

    now = datetime.utcnow()
    today = date.today()
    user = UserDB(id="flex-feed-user", email="flex@example.test", password_hash="unused", is_verified=True)
    profile = UserTravelProfileDB(user_id=user.id, origin_airports=["VIE"], budget_comfort_zone="flexible")
    db_session.add_all([
        user, profile,
        CachedRoundTripDB(origin_code="VIE", destination_code="KEF",
                          departure_date=today + timedelta(days=25), return_date=today + timedelta(days=32),
                          price=825, currency="EUR", observed_at=now, price_seen_at=now),
    ])
    db_session.commit()
    feed = build_opportunity_feed(db_session, profile, user.id)
    assert len(feed.trips) == 1
    assert "Over budget" not in feed.trips[0].tags
