"""Cross-site request forgery protection.

The property under test: a third-party page must not be able to act as a
signed-in traveller by provoking their browser into sending a request that
carries their cookies.
"""

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.security import reset_rate_limits
from app.security.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    issue_token,
    token_is_valid,
)
from app.auth.security import ACCESS_COOKIE_NAME


pytestmark = pytest.mark.raw_csrf


@pytest.fixture(autouse=True)
def clean_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Token mechanics --------------------------------------------------------

def test_an_issued_token_validates():
    assert token_is_valid(issue_token())


def test_a_token_this_deployment_never_issued_is_rejected():
    """Signed, not plain, double-submit: a planted cookie is not enough."""
    assert token_is_valid("attacker-chosen-value.deadbeef") is False
    assert token_is_valid("no-signature") is False
    assert token_is_valid("") is False
    assert token_is_valid(None) is False


def test_a_token_is_handed_out_to_a_fresh_browser(client):
    response = client.get("/health")

    assert CSRF_COOKIE_NAME in response.cookies
    assert token_is_valid(response.cookies[CSRF_COOKIE_NAME])


# --- Enforcement ------------------------------------------------------------

def test_a_cookie_authenticated_write_without_a_token_is_refused(client):
    """The attack: a third-party page provokes the browser into posting."""
    client.cookies.set(ACCESS_COOKIE_NAME, "a-session-cookie")

    response = client.patch("/auth/me", json={"displayName": "hacked"})

    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


def test_a_mismatched_token_is_refused(client):
    client.cookies.set(ACCESS_COOKIE_NAME, "a-session-cookie")
    client.cookies.set(CSRF_COOKIE_NAME, issue_token())

    response = client.patch(
        "/auth/me",
        json={"displayName": "hacked"},
        headers={CSRF_HEADER_NAME: issue_token()},  # a different valid token
    )

    assert response.status_code == 403
    assert "mismatch" in response.json()["detail"].lower()


def test_a_forged_token_presented_consistently_is_still_refused(client):
    """Cookie and header agree, but Triplet never issued the value."""
    forged = "attacker-value.not-a-real-signature"
    client.cookies.set(ACCESS_COOKIE_NAME, "a-session-cookie")
    client.cookies.set(CSRF_COOKIE_NAME, forged)

    response = client.patch(
        "/auth/me", json={"displayName": "hacked"}, headers={CSRF_HEADER_NAME: forged}
    )

    assert response.status_code == 403
    assert "invalid" in response.json()["detail"].lower()


def test_a_matching_valid_token_is_allowed_through(client):
    """Not 403: the request reaches the route and fails on its own terms."""
    token = issue_token()
    client.cookies.set(ACCESS_COOKIE_NAME, "a-session-cookie")
    client.cookies.set(CSRF_COOKIE_NAME, token)

    response = client.patch(
        "/auth/me", json={"displayName": "fine"}, headers={CSRF_HEADER_NAME: token}
    )

    assert response.status_code != 403


# --- What must NOT be blocked ----------------------------------------------

def test_reads_never_require_a_token(client):
    client.cookies.set(ACCESS_COOKIE_NAME, "a-session-cookie")

    assert client.get("/health").status_code == 200


def test_an_unauthenticated_write_is_not_blocked(client):
    """No ambient credential in play, so nothing to forge — anonymous watch
    creation and the like must keep working."""
    response = client.post("/ai/parse-trip-intent", json={"message": "a week in Rome"})

    assert response.status_code != 403


def test_the_stripe_webhook_is_not_asked_for_a_browser_token(client):
    """Stripe signs its calls; a CSRF token would just break them."""
    client.cookies.set(ACCESS_COOKIE_NAME, "a-session-cookie")

    response = client.post("/billing/webhook", content=b"{}")

    assert response.status_code != 403 or "csrf" not in response.json().get("detail", "").lower()


def test_oauth_callbacks_are_exempt(client):
    """The provider redirects the browser back; no token survives that hop."""
    from app.security.csrf import is_exempt

    assert is_exempt("/auth/oauth/google/callback")
    assert is_exempt("/billing/webhook")
    assert not is_exempt("/auth/me")
