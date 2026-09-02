"""Account email verification, and the bypass it closes.

A signed-in user creating a watch for their own account address used to skip
the double opt-in entirely — the code proved ownership by comparing strings.
That let anyone sign up as someone else's address, never confirm it, and have
Triplet start mailing a stranger. These tests hold the line that an account
address is proof of nothing until the account has proven it.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.verification import (
    RESEND_COOLDOWN_SECONDS,
    VerificationError,
    resend_verification,
    send_verification_email,
    verify_email,
)
from app.database import get_db
from app.db.models import EmailVerificationTokenDB, SavedSearchDB, UserDB
from app.main import app
from app.security import reset_rate_limits
from app.tests.test_alerts import alert_payload, override_db
from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION

VICTIM = "victim@example.com"
PASSWORD = "A-Long-Enough-Passw0rd!"


@pytest.fixture(autouse=True)
def clean_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def signup(client, email=VICTIM):
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": PASSWORD, "displayName": "Test",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        },
    )
    assert response.status_code == 200, response.text
    return response


def token_row(db_session, user_id) -> EmailVerificationTokenDB:
    return (
        db_session.query(EmailVerificationTokenDB)
        .filter(EmailVerificationTokenDB.user_id == user_id)
        .order_by(EmailVerificationTokenDB.created_at.desc())
        .first()
    )


def user_by_email(db_session, email=VICTIM) -> UserDB:
    return db_session.query(UserDB).filter(UserDB.email == email).one()


# --- Signup issues a token, and does not trust the address -------------------

def test_password_signup_creates_an_unverified_account(client, db_session):
    signup(client)
    assert user_by_email(db_session).is_verified is False


def test_signup_issues_a_verification_token(client, db_session):
    signup(client)
    row = token_row(db_session, user_by_email(db_session).id)
    assert row is not None
    assert row.used_at is None
    assert row.expires_at > datetime.utcnow()


def test_the_token_is_never_stored_in_the_clear(client, db_session, monkeypatch):
    sent: list[str] = []
    import app.auth.verification as verification

    class Capture:
        def send_email(self, to, subject, html, text):
            sent.append(text)

    monkeypatch.setattr(verification, "build_email_provider", lambda: Capture())
    signup(client)

    row = token_row(db_session, user_by_email(db_session).id)
    raw = sent[0].split("token=")[1].split()[0]
    assert raw not in row.token_hash
    assert row.token_hash != raw


# --- THE BYPASS ---------------------------------------------------------------

def test_an_unverified_account_cannot_vouch_for_its_own_address(client, db_session):
    """The attack this whole feature exists to stop.

    Sign up as someone else's address, do not confirm it, then create a watch
    for it. The watch must still demand confirmation from the address itself.
    """
    signup(client)  # signed in, is_verified False

    response = client.post("/alerts", json=alert_payload(email=VICTIM, frequency="weekly"))

    assert response.status_code == 200, response.text
    watch = db_session.get(SavedSearchDB, response.json()["id"])
    assert watch.email_verified_at is None, "unverified account was treated as proof of ownership"
    assert watch.verification_token_hash is not None, "no confirmation was demanded"


def test_a_verified_account_watching_its_own_address_needs_no_second_confirmation(
    client, db_session
):
    signup(client)
    user = user_by_email(db_session)
    user.is_verified = True
    db_session.commit()

    response = client.post("/alerts", json=alert_payload(email=VICTIM, frequency="weekly"))

    assert response.status_code == 200, response.text
    watch = db_session.get(SavedSearchDB, response.json()["id"])
    assert watch.email_verified_at is not None
    assert watch.verification_token_hash is None


def test_a_verified_account_still_cannot_vouch_for_someone_elses_address(client, db_session):
    signup(client)
    user = user_by_email(db_session)
    user.is_verified = True
    db_session.commit()

    response = client.post("/alerts", json=alert_payload(email="someone-else@example.com", frequency="weekly"))

    assert response.status_code == 200, response.text
    watch = db_session.get(SavedSearchDB, response.json()["id"])
    assert watch.email_verified_at is None
    assert watch.verification_token_hash is not None


# --- Consuming the token ------------------------------------------------------

def test_a_valid_token_verifies_the_account(client, db_session, monkeypatch):
    sent: list[str] = []
    import app.auth.verification as verification

    class Capture:
        def send_email(self, to, subject, html, text):
            sent.append(text)

    monkeypatch.setattr(verification, "build_email_provider", lambda: Capture())
    signup(client)
    raw = sent[0].split("token=")[1].split()[0]

    response = client.post("/auth/verify-email", json={"token": raw})

    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert user_by_email(db_session).is_verified is True


def test_a_token_works_only_once(client, db_session):
    signup(client)
    user = user_by_email(db_session)
    raw = send_and_capture(db_session, user)

    verify_email(db_session, raw)
    with pytest.raises(VerificationError):
        verify_email(db_session, raw)


def test_an_expired_token_is_refused(client, db_session):
    signup(client)
    user = user_by_email(db_session)
    raw = send_and_capture(db_session, user)
    # Age every token for this account rather than the newest one: created_at
    # comes from the database clock, so two rows made in the same second are
    # ordered arbitrarily and picking "the latest" is not reliable here.
    for row in db_session.query(EmailVerificationTokenDB).filter(
        EmailVerificationTokenDB.user_id == user.id
    ):
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(VerificationError):
        verify_email(db_session, raw)
    db_session.expire_all()
    assert user_by_email(db_session).is_verified is False


def test_a_forged_token_cannot_verify_anyone(client, db_session):
    signup(client)
    with pytest.raises(VerificationError):
        verify_email(db_session, "not-a-real-token-but-long-enough-to-pass")
    db_session.expire_all()
    assert user_by_email(db_session).is_verified is False


def test_every_failure_reads_the_same(client, db_session):
    """Expired, used and never-issued must be indistinguishable.

    Different messages would let someone probe which tokens exist.
    """
    signup(client)
    user = user_by_email(db_session)
    raw = send_and_capture(db_session, user)
    verify_email(db_session, raw)

    messages = set()
    for bad in (raw, "definitely-not-a-token-value-here"):
        try:
            verify_email(db_session, bad)
        except VerificationError as exc:
            messages.add(str(exc))
    assert len(messages) == 1


# --- Resend -------------------------------------------------------------------

def test_resending_supersedes_the_previous_link(client, db_session):
    signup(client)
    user = user_by_email(db_session)
    first = send_and_capture(db_session, user)

    stale = datetime.utcnow() - timedelta(seconds=RESEND_COOLDOWN_SECONDS + 5)
    for row in db_session.query(EmailVerificationTokenDB).filter(
        EmailVerificationTokenDB.user_id == user.id
    ):
        row.created_at = stale
    db_session.commit()

    assert resend_verification(db_session, user) is True
    with pytest.raises(VerificationError):
        verify_email(db_session, first)


def test_resending_is_throttled(client, db_session):
    signup(client)
    user = user_by_email(db_session)
    send_and_capture(db_session, user)

    assert resend_verification(db_session, user) is False


def test_resending_does_nothing_for_a_verified_account(client, db_session):
    signup(client)
    user = user_by_email(db_session)
    user.is_verified = True
    db_session.commit()

    assert resend_verification(db_session, user) is False


def test_the_resend_endpoint_never_says_whether_it_sent(client, db_session):
    """One reply for sent, throttled and already-verified alike."""
    signup(client)
    first = client.post("/auth/verify-email/resend")
    second = client.post("/auth/verify-email/resend")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


# --- Failure handling ---------------------------------------------------------

def test_a_mail_outage_does_not_cost_someone_their_account(client, db_session, monkeypatch):
    import app.auth.verification as verification

    class Broken:
        def send_email(self, *args, **kwargs):
            raise RuntimeError("smtp is down")

    monkeypatch.setattr(verification, "build_email_provider", lambda: Broken())

    response = client.post(
        "/auth/signup",
        json={"email": "outage@example.com", "password": PASSWORD, "displayName": "T",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        },
    )

    assert response.status_code == 200, "signup failed because email delivery failed"
    user = user_by_email(db_session, "outage@example.com")
    assert user is not None
    # The token still exists, so a resend can deliver it once mail recovers.
    assert token_row(db_session, user.id) is not None


def send_and_capture(db_session, user) -> str:
    """Issue a link and return the raw token, without going through email."""
    import app.auth.verification as verification

    captured: list[str] = []

    class Capture:
        def send_email(self, to, subject, html, text):
            captured.append(text)

    original = verification.build_email_provider
    verification.build_email_provider = lambda: Capture()
    try:
        send_verification_email(db_session, user)
    finally:
        verification.build_email_provider = original
    return captured[0].split("token=")[1].split()[0]
