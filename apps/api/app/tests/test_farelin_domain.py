from fastapi.testclient import TestClient

import app.main as main_module
from app.config import settings


def test_farelin_origin_is_accepted_and_an_untrusted_origin_is_rejected(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "allowed_origins",
        ["https://farelin.com", "https://www.farelin.com"],
    )
    client = TestClient(main_module.app)

    apex = client.post("/route-that-does-not-exist", headers={"Origin": "https://farelin.com"})
    www = client.post("/route-that-does-not-exist", headers={"Origin": "https://www.farelin.com"})
    rejected = client.post("/route-that-does-not-exist", headers={"Origin": "https://evil.example"})

    assert apex.status_code == 404
    assert www.status_code == 404
    assert rejected.status_code == 403


def test_both_exact_farelin_origins_are_configured_without_a_wildcard(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "frontend_url", "https://farelin.com")
    monkeypatch.setattr(settings, "additional_allowed_origins", "")

    origins = main_module.configured_allowed_origins()

    assert set(origins) == {"https://farelin.com", "https://www.farelin.com"}
    assert "*" not in origins


def test_farelin_alias_pair_is_added_when_apex_is_an_additional_origin(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "frontend_url", "https://triplet-web.vercel.app")
    monkeypatch.setattr(settings, "additional_allowed_origins", "https://farelin.com")

    origins = main_module.configured_allowed_origins()

    assert "https://farelin.com" in origins
    assert "https://www.farelin.com" in origins
    assert "*" not in origins
