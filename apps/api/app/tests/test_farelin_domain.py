from fastapi.testclient import TestClient

import app.main as main_module
from app.config import settings


def test_farelin_origin_is_accepted_and_an_untrusted_origin_is_rejected(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "allowed_origins",
        [
            "https://farelin.com",
            "https://www.farelin.com",
        ],
    )
    client = TestClient(main_module.app)

    apex = client.post("/route-that-does-not-exist", headers={"Origin": "https://farelin.com"})
    www = client.post("/route-that-does-not-exist", headers={"Origin": "https://www.farelin.com"})
    legacy = client.post("/route-that-does-not-exist", headers={"Origin": "https://triplet-web.vercel.app"})
    rejected = client.post("/route-that-does-not-exist", headers={"Origin": "https://evil.example"})

    assert apex.status_code == 404
    assert www.status_code == 404
    assert legacy.status_code == 403
    assert rejected.status_code == 403


def test_canonical_www_origin_is_the_only_implicit_production_origin(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "frontend_url", "https://www.farelin.com")
    monkeypatch.setattr(settings, "additional_allowed_origins", "")

    origins = main_module.configured_allowed_origins()

    assert origins == ["https://www.farelin.com"]
    assert "*" not in origins


def test_legacy_host_is_not_implicitly_trusted(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "frontend_url", "https://triplet-web.vercel.app")
    monkeypatch.setattr(settings, "additional_allowed_origins", "")

    origins = main_module.configured_allowed_origins()

    assert "https://www.farelin.com" in origins
    # FRONTEND_URL is explicit operator configuration; the old host is not
    # silently added by application code anymore.
    assert origins.count("https://triplet-web.vercel.app") == 1
    assert "*" not in origins


def test_production_api_responses_send_hsts_without_preload(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")

    response = TestClient(main_module.app).get("/health")

    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert "preload" not in response.headers["strict-transport-security"].lower()
    assert "includesubdomains" not in response.headers["strict-transport-security"].lower()


def test_local_responses_do_not_send_hsts(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "local")

    response = TestClient(main_module.app).get("/health")

    assert "strict-transport-security" not in response.headers


def test_sensitive_responses_are_not_cacheable_but_health_is_not_globally_disabled():
    client = TestClient(main_module.app)

    private = client.get("/auth/me")
    public = client.get("/health")

    assert private.status_code == 401
    assert private.headers["cache-control"] == "no-store"
    assert private.headers["pragma"] == "no-cache"
    assert public.headers.get("cache-control") != "no-store"
    assert "triplet_csrf" not in public.cookies


def test_personalizable_search_responses_are_not_cacheable():
    response = TestClient(main_module.app).post("/trips/search", json={})

    assert response.headers["cache-control"] == "no-store"
