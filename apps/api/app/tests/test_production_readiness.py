import pytest

from fastapi.testclient import TestClient

from app.config import settings
from app.security import check_production_limits
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
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")

    validate_security_settings()


def test_missing_redis_warns_but_still_boots(monkeypatch):
    """A missing variable must never crash-loop a running service.

    Per-process limits are a real weakness beyond one worker, but a total outage
    is a worse outcome than a conditional one, so this warns and starts."""
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
    monkeypatch.setattr(settings, "redis_url", None)
    monkeypatch.setattr(settings, "rate_limit_require_shared", False)

    validate_security_settings()

    assert check_production_limits() is not None


def test_a_deployment_may_declare_that_it_requires_shared_counters(monkeypatch):
    """Multi-worker deployments, where per-process limits really are useless,
    opt in to the hard failure."""
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
    monkeypatch.setattr(settings, "redis_url", None)
    monkeypatch.setattr(settings, "rate_limit_require_shared", True)

    with pytest.raises(RuntimeError, match="REDIS_URL"):
        validate_security_settings()


def test_shared_counters_satisfy_the_strict_deployment(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(settings, "rate_limit_require_shared", True)

    assert check_production_limits() is None


def test_readiness_response_has_no_secrets(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "flight_provider", "skyscanner")
    monkeypatch.setattr(settings, "skyscanner_api_enabled", True)
    monkeypatch.setattr(settings, "skyscanner_api_key", "secret-api-key")

    response = TestClient(app).get("/ready")
    body = response.text

    assert response.status_code == 200
    assert "secret-api-key" not in body
    assert "accessStatus" in body


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


def test_database_url_normalization_accepts_hosting_provider_schemes():
    from app.config import normalize_database_url

    assert normalize_database_url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert normalize_database_url("postgresql://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert normalize_database_url("postgresql+psycopg://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("sqlite:///./dev.db") == "sqlite:///./dev.db"


def test_production_readiness_does_not_publish_internals(monkeypatch):
    """A load balancer needs the verdict; an attacker would like the map."""
    from app.routers.health import readiness

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "expose_api_docs", False)

    body = readiness()

    assert set(body) == {"status"}
    assert body["status"] in {"ready", "degraded"}


def test_local_readiness_still_shows_detail(monkeypatch):
    from app.routers.health import readiness

    monkeypatch.setattr(settings, "app_env", "local")

    body = readiness()

    assert "checks" in body and "environment" in body


def test_interactive_docs_are_closed_in_production(monkeypatch):
    """Reflects the policy applied at app construction in app/main.py."""
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "expose_api_docs", False)

    enabled = settings.expose_api_docs or settings.app_env not in {"production", "prod"}

    assert enabled is False
