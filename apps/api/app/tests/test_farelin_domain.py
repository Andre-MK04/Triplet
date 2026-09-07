from fastapi.testclient import TestClient

import app.main as main_module


def test_farelin_origin_is_accepted_and_an_untrusted_origin_is_rejected(monkeypatch):
    monkeypatch.setattr(main_module, "allowed_origins", ["https://farelin.com"])
    client = TestClient(main_module.app)

    accepted = client.post("/route-that-does-not-exist", headers={"Origin": "https://farelin.com"})
    rejected = client.post("/route-that-does-not-exist", headers={"Origin": "https://evil.example"})

    assert accepted.status_code == 404
    assert rejected.status_code == 403

