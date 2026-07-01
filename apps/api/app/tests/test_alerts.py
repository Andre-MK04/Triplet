from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.alerts.token_utils import hash_token, verify_token
from app.config import settings
from app.database import get_db
from app.db.models import AlertDeliveryDB, AlertRunDB, SavedSearchDB
from app.main import app


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def alert_payload(**overrides):
    payload = {
        "email": "traveler@example.com",
        "name": "July Spain ideas",
        "originAirports": ["VIE", "ZAG"],
        "startDate": "2026-07-01",
        "endDate": "2026-07-31",
        "minTripLengthDays": 5,
        "maxTripLengthDays": 7,
        "maxBudget": 180,
        "maxGroundTransferHours": 4,
        "tripStyle": "two nearby cities",
        "directOnly": False,
        "includeBaggage": False,
        "frequency": "daily",
    }
    payload.update(overrides)
    return payload


def create_alert(client):
    response = client.post("/alerts", json=alert_payload())
    assert response.status_code == 200
    return response.json()


def token_from_url(url: str) -> str:
    return url.rsplit("token=", 1)[1]


def test_create_saved_search_generates_urls_and_hashes_tokens(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    data = create_alert(client)
    row = db_session.get(SavedSearchDB, data["id"])
    app.dependency_overrides.clear()

    assert data["manageUrl"]
    assert data["unsubscribeUrl"]
    assert row.manage_token_hash
    assert row.unsubscribe_token_hash
    assert token_from_url(data["manageUrl"]) not in row.manage_token_hash
    assert verify_token(token_from_url(data["manageUrl"]), row.manage_token_hash)


def test_create_saved_search_validates_email_and_dates(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    bad_email = client.post("/alerts", json=alert_payload(email="missing-at"))
    bad_dates = client.post("/alerts", json=alert_payload(startDate="2026-08-01", endDate="2026-07-01"))
    app.dependency_overrides.clear()

    assert bad_email.status_code == 422
    assert bad_dates.status_code == 400


def test_get_preview_and_delete_alert_require_valid_token(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    created = create_alert(client)
    token = token_from_url(created["manageUrl"])

    bad = client.get(f"/alerts/{created['id']}?token=bad")
    fetched = client.get(f"/alerts/{created['id']}?token={token}")
    preview = client.post(f"/alerts/{created['id']}/preview?token={token}")
    deleted = client.delete(f"/alerts/{created['id']}?token={token}")
    row = db_session.get(SavedSearchDB, created["id"])
    app.dependency_overrides.clear()

    assert bad.status_code == 403
    assert fetched.status_code == 200
    assert preview.status_code == 200
    assert preview.json()["matchingTrips"]
    assert deleted.status_code == 200
    assert row.is_active is False


def test_token_hash_verification_rejects_wrong_token():
    token_hash = hash_token("correct")

    assert verify_token("correct", token_hash) is True
    assert verify_token("wrong", token_hash) is False


def test_alert_run_sends_first_notification_and_logs_rows(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "email_provider", "console")
    created = create_alert(client)
    token = token_from_url(created["manageUrl"])

    response = client.post(f"/alerts/{created['id']}/run?token={token}")
    run_count = db_session.query(AlertRunDB).count()
    delivery_count = db_session.query(AlertDeliveryDB).count()
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["notificationSent"] is True
    assert response.json()["resultCount"] > 0
    assert run_count == 1
    assert delivery_count == 1


def test_alert_run_skips_same_result_inside_cooldown(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "email_provider", "console")
    created = create_alert(client)
    token = token_from_url(created["manageUrl"])

    first = client.post(f"/alerts/{created['id']}/run?token={token}")
    second = client.post(f"/alerts/{created['id']}/run?token={token}")
    app.dependency_overrides.clear()

    assert first.json()["notificationSent"] is True
    assert second.json()["notificationSent"] is False


def test_improved_price_sends_notification_after_cooldown(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "email_provider", "console")
    created = create_alert(client)
    token = token_from_url(created["manageUrl"])
    row = db_session.get(SavedSearchDB, created["id"])
    row.last_notified_at = datetime.utcnow() - timedelta(hours=25)
    row.last_best_price = 250
    db_session.commit()

    response = client.post(f"/alerts/{created['id']}/run?token={token}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["notificationSent"] is True


def test_run_due_is_dev_only(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    create_alert(client)

    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", False)
    disabled = client.post("/alerts/run-due")
    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", True)
    enabled = client.post("/alerts/run-due")
    app.dependency_overrides.clear()

    assert disabled.status_code == 404
    assert enabled.status_code == 200
