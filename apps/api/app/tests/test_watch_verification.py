"""Email ownership for watches.

A watch names an address that Triplet will then email repeatedly. Anonymous
creation used to activate immediately, so anyone could point Triplet's fare
mail at an address they do not control — and the victim's only clue would be
the unsubscribe link at the bottom. These tests hold the line that an address
has to say yes first.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.alerts.service import AlertValidationError, SavedSearchNotFoundError, SavedSearchService
from app.config import settings
from app.database import get_db
from app.db.models import SavedSearchDB
from app.main import app
from app.security import reset_rate_limits
from app.tests.test_alerts import alert_payload, override_db, token_from_url


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


def created_row(db_session, data) -> SavedSearchDB:
    return db_session.get(SavedSearchDB, data["id"])


def test_an_anonymous_watch_starts_unverified(client, db_session):
    data = client.post("/alerts", json=alert_payload()).json()

    row = created_row(db_session, data)
    assert row.email_verified_at is None
    assert row.verification_token_hash is not None
    assert row.verification_expires_at is not None


def test_an_unverified_watch_is_never_due(client, db_session):
    """The scheduler must not pick it up at all — not send-then-suppress."""
    client.post("/alerts", json=alert_payload())

    due = SavedSearchService(db_session).list_due_saved_searches()

    assert due == []


def test_an_unverified_watch_refuses_to_deliver_even_when_called_directly(client, db_session):
    """Defence in depth: delivery is where the irreversible side effect is."""
    data = client.post("/alerts", json=alert_payload()).json()
    row = created_row(db_session, data)
    service = SavedSearchService(db_session)

    with pytest.raises(AlertValidationError, match="not been confirmed"):
        service._send_delivery(row, run=None, output=None)


def test_confirming_activates_the_watch(client, db_session, monkeypatch):
    token = _capture_verification_token(client, db_session, monkeypatch)

    response = client.post(f"/alerts/verify?token={token}")

    assert response.status_code == 200
    db_session.expire_all()
    row = db_session.query(SavedSearchDB).first()
    assert row.email_verified_at is not None
    assert SavedSearchService(db_session).list_due_saved_searches() != [] or row.is_active


def test_a_confirmation_token_works_only_once(client, db_session, monkeypatch):
    token = _capture_verification_token(client, db_session, monkeypatch)
    assert client.post(f"/alerts/verify?token={token}").status_code == 200

    again = client.post(f"/alerts/verify?token={token}")

    assert again.status_code == 404


def test_an_expired_confirmation_is_refused(client, db_session, monkeypatch):
    token = _capture_verification_token(client, db_session, monkeypatch)
    row = db_session.query(SavedSearchDB).first()
    row.verification_expires_at = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    response = client.post(f"/alerts/verify?token={token}")

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_an_unknown_token_is_refused(client):
    assert client.post("/alerts/verify?token=not-a-real-token").status_code == 404


def test_resending_invalidates_the_previous_link(client, db_session, monkeypatch):
    first = _capture_verification_token(client, db_session, monkeypatch)
    data = db_session.query(SavedSearchDB).first()
    manage = _manage_token(client, db_session)

    client.post(f"/alerts/{data.id}/resend-verification?token={manage}")

    # The superseded link must not still activate the watch.
    assert client.post(f"/alerts/verify?token={first}").status_code == 404


def test_one_address_cannot_accumulate_unlimited_pending_watches(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "watch_max_unverified_per_email", 2)

    assert client.post("/alerts", json=alert_payload()).status_code == 200
    assert client.post("/alerts", json=alert_payload()).status_code == 200
    blocked = client.post("/alerts", json=alert_payload())

    assert blocked.status_code == 400
    # Must not confirm to a stranger whether this address is known to Triplet.
    detail = blocked.json()["detail"].lower()
    assert "already" in detail
    assert "registered" not in detail and "account" not in detail


def test_stale_unverified_watches_are_purged(client, db_session, monkeypatch):
    client.post("/alerts", json=alert_payload())
    row = db_session.query(SavedSearchDB).first()
    row.created_at = datetime.utcnow() - timedelta(
        hours=settings.watch_unverified_retention_hours + 1
    )
    db_session.commit()

    removed = SavedSearchService(db_session).purge_stale_unverified()

    assert removed == 1
    assert db_session.query(SavedSearchDB).count() == 0


def test_a_confirmed_watch_is_not_purged(client, db_session, monkeypatch):
    token = _capture_verification_token(client, db_session, monkeypatch)
    client.post(f"/alerts/verify?token={token}")
    row = db_session.query(SavedSearchDB).first()
    row.created_at = datetime.utcnow() - timedelta(days=365)
    db_session.commit()

    assert SavedSearchService(db_session).purge_stale_unverified() == 0


def test_alert_creation_is_rate_limited(client):
    limit = settings.rate_limit_alerts_per_window
    for _ in range(limit):
        client.post("/alerts", json=alert_payload())

    response = client.post("/alerts", json=alert_payload())

    assert response.status_code == 429
    assert response.headers.get("Retry-After")


def test_resend_is_rate_limited(client, db_session, monkeypatch):
    """The endpoint that causes mail to reach an unconfirmed address."""
    _capture_verification_token(client, db_session, monkeypatch)
    row = db_session.query(SavedSearchDB).first()
    manage = _manage_token(client, db_session)
    reset_rate_limits()

    statuses = [
        client.post(f"/alerts/{row.id}/resend-verification?token={manage}").status_code
        for _ in range(settings.rate_limit_alerts_per_window + 2)
    ]

    assert 429 in statuses


# --- helpers ---------------------------------------------------------------

_SENT: list[tuple[str, str]] = []


def _capture_verification_token(client, db_session, monkeypatch) -> str:
    """Create a watch and recover the token the email would have carried.

    The token is only ever stored hashed, so the test reads it the way the
    recipient does — out of the outgoing message.
    """
    _SENT.clear()

    class Recorder:
        provider_name = "test"

        def send_email(self, to, subject, html, text):
            _SENT.append((subject, text))

    monkeypatch.setattr("app.alerts.service.build_email_provider", lambda: Recorder())
    client.post("/alerts", json=alert_payload())
    assert _SENT, "no verification email was sent"
    text = _SENT[-1][1]
    return text.split("token=", 1)[1].split()[0].strip()


def _manage_token(client, db_session) -> str:
    row = db_session.query(SavedSearchDB).first()
    service = SavedSearchService(db_session)
    from app.alerts.token_utils import generate_token, hash_token

    token = generate_token()
    row.manage_token_hash = hash_token(token)
    db_session.commit()
    return token
