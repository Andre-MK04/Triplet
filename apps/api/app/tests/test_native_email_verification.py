"""Native email verification stays on the API that issued the app session."""

import re
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.verification import NATIVE_CODE_MAX_ATTEMPTS
from app.database import get_db
from app.db.models import (
    EmailVerificationTokenDB,
    NativeEmailVerificationCodeDB,
    UserDB,
)
from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from app.main import app

PASSWORD = "A-Long-Enough-Passw0rd!"


class CapturingProvider:
    provider_name = "test"
    delivers = True

    def __init__(self):
        self.messages: list[tuple[str, str, str]] = []

    def send_email(self, to, subject, html, text, **_kwargs):
        self.messages.append((to, subject, text))
        return "message-id"


def _client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def _signup(client, email="native@example.com"):
    return client.post(
        "/auth/native/signup",
        json={
            "email": email,
            "password": PASSWORD,
            "displayName": "Native Tester",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        },
    )


def _code(provider: CapturingProvider, index: int = -1) -> str:
    match = re.search(r"\b(\d{6})\b", provider.messages[index][2])
    assert match
    return match.group(1)


def test_native_signup_sends_code_without_creating_a_web_link(db_session, monkeypatch):
    import app.auth.verification as verification

    provider = CapturingProvider()
    monkeypatch.setattr(verification, "build_email_provider", lambda: provider)
    client = _client(db_session)

    response = _signup(client)
    user = db_session.scalar(select(UserDB).where(UserDB.email == "native@example.com"))

    assert response.status_code == 200, response.text
    assert len(provider.messages) == 1
    assert provider.messages[0][1] == "Your Farelin verification code"
    assert db_session.scalar(
        select(EmailVerificationTokenDB).where(EmailVerificationTokenDB.user_id == user.id)
    ) is None
    record = db_session.scalar(
        select(NativeEmailVerificationCodeDB).where(
            NativeEmailVerificationCodeDB.user_id == user.id
        )
    )
    assert record is not None
    assert _code(provider) not in record.code_hash
    app.dependency_overrides.clear()


def test_authenticated_native_user_can_confirm_the_emailed_code(db_session, monkeypatch):
    import app.auth.verification as verification

    provider = CapturingProvider()
    monkeypatch.setattr(verification, "build_email_provider", lambda: provider)
    client = _client(db_session)
    signup = _signup(client)
    access = signup.json()["accessToken"]

    response = client.post(
        "/auth/native/verify-email/confirm",
        json={"code": _code(provider)},
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["user"]["isVerified"] is True
    app.dependency_overrides.clear()


def test_requesting_a_new_code_retires_the_previous_code(db_session, monkeypatch):
    import app.auth.routes as auth_routes
    import app.auth.verification as verification

    provider = CapturingProvider()
    monkeypatch.setattr(verification, "build_email_provider", lambda: provider)
    monkeypatch.setattr(auth_routes, "build_email_provider", lambda: provider)
    client = _client(db_session)
    signup = _signup(client).json()
    first_code = _code(provider)
    first_record = db_session.scalar(select(NativeEmailVerificationCodeDB))
    first_record.created_at = datetime.utcnow() - timedelta(minutes=2)
    db_session.commit()
    headers = {"Authorization": f"Bearer {signup['accessToken']}"}

    requested = client.post("/auth/native/verify-email/request", headers=headers)
    stale = client.post(
        "/auth/native/verify-email/confirm",
        json={"code": first_code},
        headers=headers,
    )
    fresh = client.post(
        "/auth/native/verify-email/confirm",
        json={"code": _code(provider)},
        headers=headers,
    )

    assert requested.status_code == 200
    assert requested.json()["deliveryAccepted"] is True
    assert stale.status_code == 400
    assert fresh.status_code == 200
    app.dependency_overrides.clear()


def test_native_code_confirmation_requires_a_session(db_session):
    client = _client(db_session)
    response = client.post(
        "/auth/native/verify-email/confirm",
        json={"code": "123456"},
    )
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_code_cannot_verify_a_different_signed_in_account(db_session, monkeypatch):
    import app.auth.verification as verification

    provider = CapturingProvider()
    monkeypatch.setattr(verification, "build_email_provider", lambda: provider)
    client = _client(db_session)
    first = _signup(client, "first@example.com").json()
    first_code = _code(provider)
    second = _signup(client, "second@example.com").json()

    response = client.post(
        "/auth/native/verify-email/confirm",
        json={"code": first_code},
        headers={"Authorization": f"Bearer {second['accessToken']}"},
    )

    assert response.status_code == 400
    assert first["user"]["isVerified"] is False
    assert second["user"]["isVerified"] is False
    app.dependency_overrides.clear()


def test_expired_native_code_is_rejected(db_session, monkeypatch):
    import app.auth.verification as verification

    provider = CapturingProvider()
    monkeypatch.setattr(verification, "build_email_provider", lambda: provider)
    client = _client(db_session)
    signup = _signup(client).json()
    record = db_session.scalar(select(NativeEmailVerificationCodeDB))
    record.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    response = client.post(
        "/auth/native/verify-email/confirm",
        json={"code": _code(provider)},
        headers={"Authorization": f"Bearer {signup['accessToken']}"},
    )

    assert response.status_code == 400
    app.dependency_overrides.clear()


def test_native_code_locks_after_five_wrong_attempts(db_session, monkeypatch):
    import app.auth.verification as verification

    provider = CapturingProvider()
    monkeypatch.setattr(verification, "build_email_provider", lambda: provider)
    client = _client(db_session)
    signup = _signup(client).json()
    headers = {"Authorization": f"Bearer {signup['accessToken']}"}
    actual_code = _code(provider)

    for _ in range(NATIVE_CODE_MAX_ATTEMPTS):
        assert client.post(
            "/auth/native/verify-email/confirm",
            json={"code": "000000" if actual_code != "000000" else "999999"},
            headers=headers,
        ).status_code == 400

    locked = client.post(
        "/auth/native/verify-email/confirm",
        json={"code": actual_code},
        headers=headers,
    )
    assert locked.status_code == 400
    record = db_session.scalar(select(NativeEmailVerificationCodeDB))
    assert record.failed_attempts == NATIVE_CODE_MAX_ATTEMPTS
    assert record.used_at is not None
    app.dependency_overrides.clear()
