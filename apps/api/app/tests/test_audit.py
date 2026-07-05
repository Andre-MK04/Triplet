from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import get_db
from app.db.models import AuditEventDB
from app.main import app


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def events(db_session, action: str) -> list[AuditEventDB]:
    return list(db_session.scalars(select(AuditEventDB).where(AuditEventDB.action == action)))


def signup(client, email="audit-tester@example.com"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": "Strong-pass-123!", "displayName": "Audit Tester"},
    )


def test_signup_login_and_password_change_are_audited(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    signup(client)
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "audit-tester@example.com", "password": "Strong-pass-123!"})
    client.post(
        "/auth/change-password",
        json={"currentPassword": "Strong-pass-123!", "newPassword": "Even-stronger-456!"},
    )

    signup_events = events(db_session, "auth.signup")
    assert len(signup_events) == 1
    assert signup_events[0].user_id
    assert len(events(db_session, "auth.logout")) == 1
    assert len(events(db_session, "auth.login")) == 1
    assert len(events(db_session, "auth.password_changed")) == 1

    app.dependency_overrides.clear()


def test_failed_login_is_audited_without_user_id(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    client.post("/auth/login", json={"email": "nobody@example.com", "password": "Wrong-pass-123!"})

    failed = events(db_session, "auth.login_failed")
    assert len(failed) == 1
    assert failed[0].user_id is None

    app.dependency_overrides.clear()


def test_watch_and_profile_changes_are_audited(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    signup(client, email="audit-watcher@example.com")

    client.put(
        "/me/travel-profile",
        json={
            "originAirports": ["VIE"],
            "preferredTripLengthMin": 4,
            "preferredTripLengthMax": 8,
        },
    )
    created = client.post(
        "/me/saved-searches",
        json={
            "email": "ignored@example.com",
            "name": "Audit watch",
            "originAirports": ["VIE", "ZAG"],
            "startDate": "2026-08-01",
            "endDate": "2026-08-31",
            "minTripLengthDays": 5,
            "maxTripLengthDays": 7,
            "maxBudget": 220,
            "maxGroundTransferHours": 4,
            "tripStyle": "two nearby cities",
            "frequency": "daily",
        },
    )
    watch_id = created.json()["id"]
    client.delete(f"/me/saved-searches/{watch_id}")

    assert len(events(db_session, "profile.travel_profile_updated")) == 1
    created_events = events(db_session, "watch.created")
    assert len(created_events) == 1
    assert created_events[0].event_metadata == {"watch_id": watch_id}
    assert len(events(db_session, "watch.deleted")) == 1

    app.dependency_overrides.clear()


def test_audit_metadata_never_contains_secret_shaped_keys(db_session):
    from app.audit import record_audit_event

    record_audit_event(
        db_session,
        "test.event",
        user_id="u-1",
        commit=True,
        safe_field="ok",
        password="should-be-dropped",
        api_token="should-be-dropped",
    )

    row = events(db_session, "test.event")[0]
    assert row.event_metadata == {"safe_field": "ok"}
