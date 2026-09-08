"""Resend HTTPS delivery for hosts where outbound SMTP is blocked."""

import httpx
import pytest

from app.alerts.email import EmailProviderError, ResendEmailProvider
from app.config import settings


@pytest.fixture()
def resend_config(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_secret_test_key")
    monkeypatch.setattr(settings, "email_from", "alerts@farelin.test")
    monkeypatch.setattr(settings, "email_reply_to", "hello@farelin.test")
    monkeypatch.setattr(settings, "app_name", "Farelin")


def test_resend_sends_over_https_without_exposing_the_key(resend_config, monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return httpx.Response(200, json={"id": "email_123"})

    monkeypatch.setattr(httpx, "post", fake_post)

    provider_id = ResendEmailProvider().send_email(
        "traveller@example.com",
        "A fare",
        "<p>Deal</p>",
        "Deal",
        idempotency_key="watch-notification/watch-1/run-1",
    )

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["timeout"] == 10.0
    assert captured["json"] == {
        "from": "Farelin <alerts@farelin.test>",
        "to": ["traveller@example.com"],
        "subject": "A fare",
        "html": "<p>Deal</p>",
        "text": "Deal",
        "reply_to": "hello@farelin.test",
    }
    assert captured["headers"]["Authorization"] == "Bearer re_secret_test_key"
    assert captured["headers"]["Idempotency-Key"] == "watch-notification/watch-1/run-1"
    assert "re_secret_test_key" not in str(captured["json"])
    assert provider_id == "email_123"


def test_resend_rejects_unsafe_or_oversized_idempotency_keys(resend_config):
    with pytest.raises(EmailProviderError, match="idempotency"):
        ResendEmailProvider().send_email("a@example.com", "S", "H", "T", idempotency_key="x" * 257)
    with pytest.raises(EmailProviderError, match="idempotency"):
        ResendEmailProvider().send_email("a@example.com", "S", "H", "T", idempotency_key="bad\nkey")


def test_resend_rejection_becomes_a_safe_provider_error(resend_config, monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(403, text="recipient@example.com was rejected"),
    )

    with pytest.raises(EmailProviderError, match="HTTP 403") as caught:
        ResendEmailProvider().send_email("recipient@example.com", "Subject", "html", "text")

    assert "recipient@example.com" not in str(caught.value)


def test_resend_network_timeout_becomes_a_provider_error(resend_config, monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(httpx, "post", timeout)

    with pytest.raises(EmailProviderError, match="could not be reached"):
        ResendEmailProvider().send_email("recipient@example.com", "Subject", "html", "text")
