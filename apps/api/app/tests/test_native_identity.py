import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.auth import native_identity as identity
from app.auth.oauth import OAuthProviderError
from app.auth.routes import NativeIdentityRequest
from app.config import settings
from app.database import get_db
from app.db.models import NativeAuthChallengeDB, UserDB, UserOAuthAccountDB
from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def signing(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(identity, "_jwks", lambda _: SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key())))
    monkeypatch.setattr(settings, "native_google_client_ids", "ios-test-audience")
    monkeypatch.setattr(settings, "native_apple_client_ids", "com.farelin.test")
    monkeypatch.setattr(settings, "apple_oauth_team_id", "test-team")
    monkeypatch.setattr(settings, "apple_oauth_key_id", "test-key")
    monkeypatch.setattr(settings, "apple_oauth_private_key", "not-used-by-mocked-exchange")
    def encode(provider="google", **overrides):
        claims = {"sub": "provider-subject", "iss": "https://accounts.google.com" if provider == "google" else "https://appleid.apple.com",
            "aud": "ios-test-audience" if provider == "google" else "com.farelin.test",
            "iat": int(time.time()), "exp": int(time.time()) + 300,
            "email": "traveler@gmail.com", "email_verified": True}
        claims.update(overrides)
        return jwt.encode(claims, key, algorithm="RS256")
    return encode


@pytest.mark.parametrize("override", [{"aud": "wrong-app"}, {"iss": "https://attacker.example"}, {"exp": 1}, {"sub": ""}])
def test_wrong_claims_are_rejected(signing, override):
    with pytest.raises(OAuthProviderError): identity.verify_token("google", signing(**override))


def test_signature_is_required(signing):
    token = jwt.encode({"sub": "attacker", "aud": "ios-test-audience"}, "not-a-secret" * 4, algorithm="HS256")
    with pytest.raises(OAuthProviderError): identity.verify_token("google", token)


def test_google_native_signup_returns_own_bearer_session_and_reuses_account(db_session, signing):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        payload = {"idToken": signing(), "intent": "signup", "acceptedTermsVersion": CURRENT_TERMS_VERSION,
                   "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION}
        response = client.post("/auth/native/oauth/google", json=payload)
        assert response.status_code == 200
        assert response.json()["user"]["isVerified"] is True
        assert "set-cookie" not in response.headers
        assert response.json()["tokenType"] == "Bearer"
        user_id = response.json()["user"]["id"]
        second = client.post("/auth/native/oauth/google", json={"idToken": signing()})
        assert second.status_code == 200
        assert second.json()["user"]["id"] == user_id
        assert db_session.query(UserOAuthAccountDB).count() == 1
    finally: app.dependency_overrides.clear()


def test_new_identity_requires_current_legal_consent(db_session, signing):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).post("/auth/native/oauth/google", json={"idToken": signing(), "intent": "signup"})
        assert response.status_code == 400
        assert db_session.query(UserDB).count() == 0
    finally: app.dependency_overrides.clear()


def test_disabled_account_cannot_return_through_native_oauth(db_session, signing):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.post("/auth/native/oauth/google", json={"idToken": signing(), "intent": "signup",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION, "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION})
        assert response.status_code == 200
        user = db_session.get(UserDB, response.json()["user"]["id"])
        user.is_active = False
        db_session.commit()
        blocked = client.post("/auth/native/oauth/google", json={"idToken": signing()})
        assert blocked.status_code == 400
        assert "accessToken" not in blocked.json()
    finally: app.dependency_overrides.clear()


def test_unverified_provider_email_is_rejected(db_session, signing):
    import asyncio
    with pytest.raises(OAuthProviderError):
        asyncio.run(identity.verified_profile(db_session, "google", NativeIdentityRequest(idToken=signing(email_verified=False))))


def test_apple_nonce_consumed_once_and_refresh_is_encrypted(db_session, signing, monkeypatch):
    import asyncio
    challenge = identity.new_challenge(db_session)
    row = db_session.get(NativeAuthChallengeDB, challenge["id"])
    token = signing("apple", nonce=row.nonce_hash)
    monkeypatch.setattr(identity, "apple_client_secret", lambda _: "mock-client-secret")
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=200, json=lambda: {"id_token": token, "refresh_token": "test-provider-refresh"})
    monkeypatch.setattr(identity.httpx, "AsyncClient", lambda **_: Client())
    payload = NativeIdentityRequest(idToken=token, challengeId=challenge["id"], authorizationCode="mock-code")
    profile, encrypted, audience = asyncio.run(identity.verified_profile(db_session, "apple", payload))
    assert profile.email_verified and audience == "com.farelin.test"
    assert encrypted != "test-provider-refresh"
    assert identity.token_cipher().decrypt(encrypted.encode()) == b"test-provider-refresh"
    db_session.commit()
    with pytest.raises(OAuthProviderError): asyncio.run(identity.verified_profile(db_session, "apple", payload))


def test_apple_wrong_nonce_rejected_before_provider_call(db_session, signing):
    import asyncio
    challenge = identity.new_challenge(db_session)
    with pytest.raises(OAuthProviderError):
        asyncio.run(identity.verified_profile(db_session, "apple", NativeIdentityRequest(
            idToken=signing("apple", nonce="wrong"), challengeId=challenge["id"], authorizationCode="mock")))


def test_provider_status_does_not_disclose_credentials():
    response = TestClient(app).get("/auth/native/providers")
    assert response.json() == {"google": False, "apple": False}


def test_expired_apple_challenge_rejected_before_exchange(db_session, signing):
    import asyncio
    from datetime import datetime, timedelta
    challenge = identity.new_challenge(db_session)
    row = db_session.get(NativeAuthChallengeDB, challenge["id"])
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    with pytest.raises(OAuthProviderError):
        asyncio.run(identity.verified_profile(db_session, "apple", NativeIdentityRequest(
            idToken=signing("apple", nonce=row.nonce_hash), challengeId=row.id, authorizationCode="mock")))


@pytest.mark.parametrize("body", [[], {"refresh_token": 42}, {"refresh_token": ""}])
def test_malformed_apple_exchange_is_a_clean_error(db_session, signing, monkeypatch, body):
    import asyncio
    challenge = identity.new_challenge(db_session)
    row = db_session.get(NativeAuthChallengeDB, challenge["id"])
    monkeypatch.setattr(identity, "apple_client_secret", lambda _: "mock-client-secret")
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=200, json=lambda: body)
    monkeypatch.setattr(identity.httpx, "AsyncClient", lambda **_: Client())
    with pytest.raises(OAuthProviderError):
        asyncio.run(identity.verified_profile(db_session, "apple", NativeIdentityRequest(
            idToken=signing("apple", nonce=row.nonce_hash), challengeId=row.id, authorizationCode="mock")))
    assert row.consumed_at is None
