from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.db.models import PushDeviceDB, PushDeliveryDB, AlertRunDB, SavedSearchDB, UserDB
from app.main import app
from app.notifications import service as push
from app.privacy.service import erase_user, export_user_data
from app.alerts.service import SavedSearchService
from app.alerts.schemas import CreateSavedSearchRequest, UpdateSavedSearchRequest
from app.legal import CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION


@pytest.fixture
def configured(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    monkeypatch.setattr(settings, "apns_enabled", True)
    monkeypatch.setattr(settings, "apns_private_key", pem)
    monkeypatch.setattr(settings, "apns_team_id", "test-team")
    monkeypatch.setattr(settings, "apns_key_id", "test-key")
    monkeypatch.setattr(settings, "apns_topic", "com.farelin.test")
    monkeypatch.setattr(settings, "apns_environment", "sandbox")


@pytest.fixture
def user(db_session):
    row = UserDB(id=str(uuid4()), email="push@example.com", password_hash="unusable", is_verified=True,
                 plan="free", subscription_status="none", is_active=True)
    db_session.add(row); db_session.commit()
    return row


@pytest.fixture
def watch(db_session, user):
    request = CreateSavedSearchRequest(email=user.email, name="Nordics", originAirports=["VIE"],
        destinationRegions=["nordics"], startDate="2026-10-01", endDate="2026-10-31", minTripLengthDays=4,
        maxTripLengthDays=7, maxBudget=400, maxGroundTransferHours=4, tripStyle="one city", frequency="weekly")
    created = SavedSearchService(db_session).create_user_saved_search(user, request)
    return db_session.get(SavedSearchDB, created.id)


def queue(db, user, watch):
    device = push.register_device(db, user.id, "a1" * 32)
    run = AlertRunDB(id=str(uuid4()), saved_search_id=watch.id, status="success", result_count=2)
    db.add(run); db.commit()
    assert push.enqueue_watch_push(db, watch, run.id) == 1
    db.commit()
    return device, run, db.scalar(select(PushDeliveryDB))


def test_disabled_push_neither_registers_implicitly_nor_consumes_outbox(db_session):
    assert push.push_configured() is False
    assert push.deliver_pending_push(db_session)["enabled"] is False


def test_device_tokens_encrypted_and_not_exported(db_session, configured, user):
    device = push.register_device(db_session, user.id, "a1" * 32)
    assert device.encrypted_token != "a1" * 32
    export = export_user_data(db_session, user)
    assert len(export["notificationDevices"]) == 1
    assert "encrypted_token" not in str(export) and "a1" * 32 not in str(export)


def test_device_cannot_be_taken_by_another_user(db_session, configured, user):
    push.register_device(db_session, user.id, "a1" * 32)
    with pytest.raises(ValueError): push.register_device(db_session, "other-user", "a1" * 32)


def test_queue_deduplicates_by_watch_event_and_device(db_session, configured, user, watch):
    device, run, _ = queue(db_session, user, watch)
    assert push.enqueue_watch_push(db_session, watch, run.id) == 0
    assert db_session.query(PushDeliveryDB).count() == 1


def test_delivery_retries_at_most_three_times(db_session, configured, user, watch, monkeypatch):
    _, _, delivery = queue(db_session, user, watch)
    monkeypatch.setattr(push, "send_to_apns", lambda *_: "retry")
    now = datetime.utcnow() + timedelta(seconds=1)
    for i in range(3):
        push.deliver_pending_push(db_session, now + timedelta(hours=i))
    db_session.refresh(delivery)
    assert delivery.attempts == 3 and delivery.status == "failed"
    push.deliver_pending_push(db_session, now + timedelta(hours=4))
    assert delivery.attempts == 3


def test_invalid_device_is_disabled(db_session, configured, user, watch, monkeypatch):
    device, _, delivery = queue(db_session, user, watch)
    monkeypatch.setattr(push, "send_to_apns", lambda *_: "invalid_device")
    push.deliver_pending_push(db_session, datetime.utcnow() + timedelta(seconds=1))
    db_session.refresh(device); db_session.refresh(delivery)
    assert not device.is_active and delivery.status == "failed"


def test_paused_watch_does_not_push(db_session, configured, user, watch, monkeypatch):
    _, _, delivery = queue(db_session, user, watch)
    watch.is_active = False; db_session.commit()
    monkeypatch.setattr(push, "send_to_apns", lambda *_: pytest.fail("Paused watch must not send"))
    push.deliver_pending_push(db_session, datetime.utcnow() + timedelta(seconds=1))
    assert delivery.status == "failed"


def test_apns_payload_generic_and_uses_stable_delivery_id(db_session, configured, user, watch, monkeypatch):
    device, _, delivery = queue(db_session, user, watch)
    calls = []
    class Client:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(status_code=200)
    monkeypatch.setattr(push.httpx, "Client", lambda **_: Client())
    assert push.send_to_apns(device, delivery) == "sent"
    kwargs = calls[0][1]
    assert kwargs["headers"]["apns-id"] == delivery.id
    assert kwargs["json"]["watchId"] == watch.id
    assert "push@example.com" not in str(kwargs["json"])
    assert "Nordics" not in str(kwargs["json"])


def test_erasure_covers_devices_and_pending_push(db_session, configured, user, watch):
    queue(db_session, user, watch)
    erase_user(db_session, user)
    assert db_session.query(PushDeviceDB).count() == 0
    assert db_session.query(PushDeliveryDB).count() == 0


def test_watch_delete_removes_outbox_and_history(db_session, configured, user, watch):
    queue(db_session, user, watch)
    SavedSearchService(db_session).delete_user_saved_search(user, watch.id)
    assert db_session.query(PushDeliveryDB).count() == 0
    assert db_session.query(AlertRunDB).count() == 0
    assert db_session.query(SavedSearchDB).count() == 0


def test_watch_detail_owner_isolation_and_edit_at_limit(db_session, configured):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        signup = {"email": "watchowner@example.com", "password": "Strong-pass-123!",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION, "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION}
        client.post("/auth/signup", json=signup)
        request = {"email": signup["email"], "originAirports": ["VIE"], "destinationRegions": ["nordics"],
            "startDate": "2026-10-01", "endDate": "2026-10-31", "minTripLengthDays": 4,
            "maxTripLengthDays": 7, "maxBudget": 400, "maxGroundTransferHours": 4,
            "tripStyle": "one city", "frequency": "weekly"}
        created = client.post("/me/saved-searches", json=request)
        assert created.status_code == 200
        id = created.json()["id"]
        detail = client.get(f"/me/saved-searches/{id}")
        assert detail.status_code == 200 and detail.json()["destinationRegions"] == ["nordics"]
        changed = client.patch(f"/me/saved-searches/{id}", json={"name": "Updated watch", "frequency": "weekly", "maxBudget": 300})
        assert changed.status_code == 200
        assert changed.json()["destinationRegions"] == ["nordics"]
        client.post("/auth/signup", json={**signup, "email": "other@example.com"})
        assert client.get(f"/me/saved-searches/{id}").status_code == 404
        assert client.delete(f"/me/saved-searches/{id}").status_code == 404
    finally: app.dependency_overrides.clear()


def test_push_endpoint_requires_confirmed_email_and_rejects_wrong_topic(db_session, configured):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        assert client.get("/me/push/status").status_code == 401
        result = client.post("/auth/native/signup", json={"email": "device@example.com", "password": "Strong-pass-123!",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION, "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION})
        headers = {"Authorization": "Bearer " + result.json()["accessToken"]}
        payload = {"token": "a1" * 32, "topic": settings.apns_topic, "environment": "sandbox"}
        assert client.post("/me/push/devices", json=payload, headers=headers).status_code == 403
        user = db_session.get(UserDB, result.json()["user"]["id"]); user.is_verified = True; db_session.commit()
        assert client.post("/me/push/devices", json={**payload, "topic": "wrong.app"}, headers=headers).status_code == 400
        registration = client.post("/me/push/devices", json=payload, headers=headers)
        assert registration.status_code == 200
        assert client.delete("/me/push/devices/unknown", headers=headers).status_code == 404
    finally: app.dependency_overrides.clear()
