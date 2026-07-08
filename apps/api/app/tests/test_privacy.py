from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import get_db
from app.db.models import (
    AuditEventDB,
    RefreshTokenSessionDB,
    SavedSearchDB,
    UserDB,
    UserTravelProfileDB,
)
from app.main import app


def override_db(db_session):
    def _override():
        yield db_session

    return _override


def make_client(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    return TestClient(app)


def signup(client, email="privacy@example.com"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": "Strong-pass-123!", "displayName": "Privacy Tester"},
    )


def seed_user_data(client):
    client.put(
        "/me/travel-profile",
        json={"originAirports": ["VIE", "ZAG"], "preferredTripLengthMin": 4, "preferredTripLengthMax": 8},
    )
    client.post(
        "/me/saved-searches",
        json={
            "email": "ignored@example.com", "name": "Watch",
            "originAirports": ["VIE"], "startDate": "2026-08-01", "endDate": "2026-08-31",
            "minTripLengthDays": 5, "maxTripLengthDays": 7, "maxBudget": 220,
            "maxGroundTransferHours": 4, "tripStyle": "one city", "frequency": "daily",
        },
    )


def test_export_returns_users_data_without_secrets(db_session):
    client = make_client(db_session)
    signup(client)
    seed_user_data(client)

    body = client.get("/me/export").json()
    assert body["account"]["email"] == "privacy@example.com"
    assert body["travelProfile"]["originAirports"] == ["VIE", "ZAG"]
    assert len(body["savedSearches"]) == 1
    # No secret material in the actual data (ignore the human-readable note).
    body.pop("note", None)
    dumped = str(body).lower()
    assert "password" not in dumped and "hash" not in dumped and "token" not in dumped

    app.dependency_overrides.clear()


def test_export_requires_login(db_session):
    client = make_client(db_session)
    assert client.get("/me/export").status_code == 401
    app.dependency_overrides.clear()


def test_erasure_removes_all_user_rows_and_logs_out(db_session):
    client = make_client(db_session)
    signup(client, email="erase-me@example.com")
    seed_user_data(client)

    user_id = db_session.scalar(select(UserDB.id).where(UserDB.email == "erase-me@example.com"))
    assert user_id

    response = client.delete("/auth/me")
    assert response.status_code == 200

    # No personal rows remain for this user in any linked table.
    for model in (UserDB, UserTravelProfileDB, SavedSearchDB, RefreshTokenSessionDB):
        remaining = db_session.scalar(
            select(func.count()).select_from(model).where(model.user_id == user_id)
            if model is not UserDB
            else select(func.count()).select_from(UserDB).where(UserDB.id == user_id)
        )
        assert remaining == 0, f"{model.__name__} still has rows for the erased user"

    # Audit trail kept but anonymised (user_id nulled), and erasure recorded.
    assert db_session.scalar(
        select(func.count()).select_from(AuditEventDB).where(AuditEventDB.user_id == user_id)
    ) == 0
    assert db_session.scalar(
        select(func.count()).select_from(AuditEventDB).where(AuditEventDB.action == "privacy.account_erased")
    ) >= 1

    # Session is gone.
    assert client.get("/auth/me").status_code == 401
    app.dependency_overrides.clear()


def test_retention_cleanup_prunes_only_old_data(db_session):
    from datetime import datetime, timedelta
    from sqlalchemy import func, select
    from app.db.models import AuditEventDB, CachedRoundTripDB
    from app.privacy.retention import cleanup

    now = datetime.utcnow()
    db_session.add(AuditEventDB(action="auth.login", created_at=now - timedelta(days=200)))
    db_session.add(AuditEventDB(action="auth.login", created_at=now - timedelta(days=5)))
    db_session.add(CachedRoundTripDB(origin_code="VIE", destination_code="CPH", departure_date=now.date(),
                                     price=100, observed_at=now - timedelta(days=10)))
    db_session.add(CachedRoundTripDB(origin_code="VIE", destination_code="ARN", departure_date=now.date(),
                                     price=120, observed_at=now))
    db_session.commit()

    summary = cleanup(db_session, now=now)
    assert summary["auditDeleted"] == 1
    assert summary["cachedDealsDeleted"] == 1
    assert db_session.scalar(select(func.count()).select_from(AuditEventDB)) == 1
    assert db_session.scalar(select(func.count()).select_from(CachedRoundTripDB)) == 1
