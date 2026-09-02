from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import get_db
from app.db.models import (
    AuditEventDB,
    CountryVisitDB,
    RefreshTokenSessionDB,
    SavedSearchDB,
    UserDB,
    UserCountryDB,
    UserTravelProfileDB,
)
from app.main import app
from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION


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
        json={"email": email, "password": "Strong-pass-123!", "displayName": "Privacy Tester",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        },
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
            "maxGroundTransferHours": 4, "tripStyle": "one city", "frequency": "weekly",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        },
    )
    client.patch("/me/travel-map/countries/IS", json={"wishlist": True})
    client.post(
        "/me/travel-map/countries/IT/visits",
        json={"startDate": "2024-08", "note": "Summer trip"},
    )


def test_export_returns_users_data_without_secrets(db_session):
    client = make_client(db_session)
    signup(client)
    seed_user_data(client)

    body = client.get("/me/export").json()
    assert body["account"]["email"] == "privacy@example.com"
    assert body["travelProfile"]["originAirports"] == ["VIE", "ZAG"]
    assert len(body["savedSearches"]) == 1
    assert {country["countryCode"] for country in body["travelMap"]["countries"]} == {"IS", "IT"}
    assert body["travelMap"]["visits"][0]["startPrecision"] == "month"
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
    for model in (
        UserDB,
        UserTravelProfileDB,
        SavedSearchDB,
        RefreshTokenSessionDB,
        UserCountryDB,
        CountryVisitDB,
    ):
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


def test_session_rows_never_keep_a_raw_ip(db_session):
    """The privacy policy says Triplet keeps a hash, not an address.

    It was untrue: refresh_token_sessions stored request.client.host verbatim,
    for a column nothing ever read.
    """
    from app.auth.service import AuthService
    from app.db.models import RefreshTokenSessionDB
    from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
    from app.auth.schemas import SignupRequest

    AuthService(db_session).signup(
        SignupRequest(
            email="ip-check@example.com",
            password="A-Long-Enough-Passw0rd!",
            acceptedTermsVersion=CURRENT_TERMS_VERSION,
            acknowledgedPrivacyVersion=CURRENT_PRIVACY_VERSION,
        ),
        user_agent="pytest",
        ip_address="203.0.113.42",
    )

    stored = [s.ip_address for s in db_session.query(RefreshTokenSessionDB).all()]
    assert stored, "expected a session row"
    for value in stored:
        assert value != "203.0.113.42"
        assert "203.0.113" not in (value or "")
