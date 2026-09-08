"""Public contact mail is delivered, bounded, and never silently discarded."""

from fastapi.testclient import TestClient

from app.alerts.email import EmailProvider, contact_recipient
from app.config import settings
from app.main import app


class CapturingProvider(EmailProvider):
    def __init__(self):
        super().__init__(provider_name="test", delivers=True)
        self.messages: list[dict[str, str]] = []

    def send_email(self, to, subject, html_body, text_body):
        self.messages.append(
            {"to": to, "subject": subject, "html": html_body, "text": text_body}
        )


def payload(**overrides):
    return {
        "name": "Ada Traveller",
        "email": "ada@example.com",
        "topic": "fare",
        "message": "The displayed fare changed when I opened the provider.",
        **overrides,
    }


def test_contact_message_is_sent_to_configured_inbox(monkeypatch):
    provider = CapturingProvider()
    monkeypatch.setattr(settings, "contact_email_to", "support@farelin.test")
    monkeypatch.setattr("app.routers.contact.build_email_provider", lambda: provider)

    response = TestClient(app).post("/contact", json=payload())

    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    assert len(provider.messages) == 1
    assert provider.messages[0]["to"] == "support@farelin.test"
    assert provider.messages[0]["subject"] == "Farelin contact · Fare or trip issue"
    assert "ada@example.com" in provider.messages[0]["text"]


def test_contact_html_escapes_user_content(monkeypatch):
    provider = CapturingProvider()
    monkeypatch.setattr(settings, "contact_email_to", "support@farelin.test")
    monkeypatch.setattr("app.routers.contact.build_email_provider", lambda: provider)

    response = TestClient(app).post(
        "/contact",
        json=payload(name="<b>Ada</b>", message="<script>alert('x')</script> is not acceptable"),
    )

    assert response.status_code == 200
    assert "<script>" not in provider.messages[0]["html"]
    assert "&lt;script&gt;" in provider.messages[0]["html"]
    assert "<b>Ada</b>" not in provider.messages[0]["html"]


def test_contact_rejects_invalid_email(monkeypatch):
    monkeypatch.setattr(settings, "contact_email_to", "support@farelin.test")

    response = TestClient(app).post("/contact", json=payload(email="not-an-address"))

    assert response.status_code == 422


def test_contact_does_not_claim_success_without_delivery(monkeypatch):
    monkeypatch.setattr(settings, "contact_email_to", "")
    monkeypatch.setattr(settings, "email_reply_to", "")

    response = TestClient(app).post("/contact", json=payload())

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_contact_recipient_falls_back_to_monitored_reply_inbox(monkeypatch):
    monkeypatch.setattr(settings, "contact_email_to", "")
    monkeypatch.setattr(settings, "email_reply_to", "hello@farelin.test")

    assert contact_recipient() == "hello@farelin.test"


def test_honeypot_submission_sends_nothing(monkeypatch):
    provider = CapturingProvider()
    monkeypatch.setattr(settings, "contact_email_to", "support@farelin.test")
    monkeypatch.setattr("app.routers.contact.build_email_provider", lambda: provider)

    response = TestClient(app).post("/contact", json=payload(website="https://spam.invalid"))

    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    assert provider.messages == []


def test_contact_has_a_tight_independent_rate_limit(monkeypatch):
    provider = CapturingProvider()
    monkeypatch.setattr(settings, "contact_email_to", "support@farelin.test")
    monkeypatch.setattr(settings, "contact_rate_limit_max_attempts", 2)
    monkeypatch.setattr("app.routers.contact.build_email_provider", lambda: provider)
    client = TestClient(app)

    assert client.post("/contact", json=payload()).status_code == 200
    assert client.post("/contact", json=payload()).status_code == 200
    limited = client.post("/contact", json=payload())

    assert limited.status_code == 429
    assert len(provider.messages) == 2
