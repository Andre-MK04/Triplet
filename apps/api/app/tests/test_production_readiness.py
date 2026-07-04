from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, validate_security_settings
from app.rate_limit import clear_rate_limits, rate_limit


def test_production_validation_rejects_insecure_defaults(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "app_secret", "dev-secret-change-me")
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:3000")
    monkeypatch.setattr(settings, "api_public_base_url", "http://localhost:8001")
    monkeypatch.setattr(settings, "auth_cookie_secure", False)

    try:
        validate_security_settings()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("production validation should reject insecure defaults")

    assert "APP_SECRET" in message
    assert "HTTPS" in message
    assert "AUTH_COOKIE_SECURE" in message


def test_production_validation_accepts_secure_minimum(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "app_secret", "not-the-dev-secret")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:pass@db/triplet")
    monkeypatch.setattr(settings, "frontend_url", "https://triplet.example")
    monkeypatch.setattr(settings, "api_public_base_url", "https://api.triplet.example")
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_samesite", "none")
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "flight_provider", "database")
    monkeypatch.setattr(settings, "billing_enabled", False)
    monkeypatch.setattr(settings, "email_provider", "console")

    validate_security_settings()


def test_readiness_response_has_no_secrets(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "flight_provider", "skyscanner")
    monkeypatch.setattr(settings, "skyscanner_api_enabled", True)
    monkeypatch.setattr(settings, "skyscanner_api_key", "secret-api-key")

    response = TestClient(app).get("/ready")
    body = response.text

    assert response.status_code == 200
    assert "secret-api-key" not in body
    assert "skyscannerApiKeyConfigured" in body


def test_generic_rate_limit_blocks_after_threshold():
    clear_rate_limits()

    class Client:
        host = "127.0.0.1"

    class Request:
        client = Client()

    limiter = rate_limit("test", max_attempts=1, window_seconds=60)
    limiter(Request())

    try:
        limiter(Request())
    except Exception as exc:
        assert getattr(exc, "status_code") == 429
    else:
        raise AssertionError("rate limit should block the second request")
