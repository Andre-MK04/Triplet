import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from svix.webhooks import Webhook

from app.config import settings
from app.database import get_db
from app.db.models import EmailEventDB, EmailSuppressionDB
from app.email_delivery import is_suppressed, recipient_hash
from app.main import app

SECRET = "whsec_dGVzdC13ZWJob29rLXNlY3JldA=="


def signed_headers(body: str, event_id: str = "msg_test_1") -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "svix-id": event_id,
        "svix-timestamp": str(int(now.timestamp())),
        "svix-signature": Webhook(SECRET).sign(event_id, now, body),
    }


def webhook_body(event_type: str = "email.bounced") -> str:
    return json.dumps({
        "type": event_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "email_id": "email_123",
            "to": ["traveller@example.com"],
            "bounce": {"type": "Permanent"},
        },
    }, separators=(",", ":"))


def client_for(db_session, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "resend_webhook_secret", SECRET)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_invalid_resend_signature_is_rejected_before_payload_is_trusted(db_session, monkeypatch):
    client = client_for(db_session, monkeypatch)
    response = client.post(
        "/webhooks/resend",
        content=webhook_body(),
        headers={"svix-id": "forged", "svix-timestamp": "1", "svix-signature": "v1,forged"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert db_session.query(EmailEventDB).count() == 0


def test_hard_bounce_is_stored_once_and_suppresses_future_mail(db_session, monkeypatch):
    client = client_for(db_session, monkeypatch)
    body = webhook_body()
    headers = signed_headers(body)

    first = client.post("/webhooks/resend", content=body, headers=headers)
    duplicate = client.post("/webhooks/resend", content=body, headers=headers)
    app.dependency_overrides.clear()

    assert first.json() == {"received": True, "processed": True}
    assert duplicate.json() == {"received": True, "processed": False}
    assert db_session.query(EmailEventDB).count() == 1
    suppression = db_session.get(EmailSuppressionDB, recipient_hash("traveller@example.com"))
    assert suppression.reason == "hard_bounce"
    assert is_suppressed(db_session, "traveller@example.com", "account") is True
    assert is_suppressed(db_session, "traveller@example.com", "watch") is True


def test_complaint_stops_optional_watch_mail_but_not_requested_account_security_mail(db_session, monkeypatch):
    client = client_for(db_session, monkeypatch)
    body = webhook_body("email.complained")
    response = client.post("/webhooks/resend", content=body, headers=signed_headers(body, "msg_complaint"))
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert is_suppressed(db_session, "traveller@example.com", "watch") is True
    assert is_suppressed(db_session, "traveller@example.com", "account") is False
