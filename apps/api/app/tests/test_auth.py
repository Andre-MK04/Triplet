from fastapi.testclient import TestClient

import pytest

from app.auth.oauth import OAUTH_STATE_COOKIE_NAME, OAuthProfile, OAuthState, generate_oauth_state
from app.auth.security import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.auth.service import AuthError, AuthService
from app.config import settings
from app.database import get_db
from app.db.models import PasswordResetTokenDB, SavedSearchDB, UserDB, UserOAuthAccountDB, UserTravelProfileDB
from app.main import app
from app.legal import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def signup_payload(**overrides):
    payload = {
        "email": "traveler@example.com",
        "password": "Strong-pass-123!",
        "displayName": "Traveler",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        }
    payload.update(overrides)
    return payload


def saved_search_payload(**overrides):
    payload = {
        "email": "ignored@example.com",
        "name": "August ideas",
        "originAirports": ["VIE", "ZAG"],
        "startDate": "2026-08-01",
        "endDate": "2026-08-31",
        "minTripLengthDays": 5,
        "maxTripLengthDays": 7,
        "maxBudget": 220,
        "maxGroundTransferHours": 4,
        "tripStyle": "two nearby cities",
        "directOnly": False,
        "includeBaggage": False,
        "frequency": "weekly",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        }
    payload.update(overrides)
    return payload


def make_client(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    return TestClient(app)


def test_signup_sets_http_only_auth_cookies_and_returns_user(db_session):
    client = make_client(db_session)

    response = client.post("/auth/signup", json=signup_payload())
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "traveler@example.com"
    set_cookie = response.headers.get("set-cookie", "")
    assert ACCESS_COOKIE_NAME in set_cookie
    assert REFRESH_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie


def test_signup_stores_password_hash_not_plaintext(db_session):
    client = make_client(db_session)

    response = client.post("/auth/signup", json=signup_payload())
    user = db_session.query(UserDB).filter(UserDB.email == "traveler@example.com").one()
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert user.password_hash
    assert user.password_hash != "Strong-pass-123!"
    # Argon2id for everything new; legacy PBKDF2 hashes are upgraded at login
    # instead (see test_password_hashing.py).
    assert user.password_hash.startswith("$argon2id$")


def test_signup_rejects_weak_password(db_session):
    client = make_client(db_session)

    response = client.post("/auth/signup", json=signup_payload(password="short"))
    app.dependency_overrides.clear()

    assert response.status_code == 400


def test_login_me_refresh_and_logout_flow(db_session):
    client = make_client(db_session)
    client.post("/auth/signup", json=signup_payload())
    client.post("/auth/logout")

    login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "Strong-pass-123!",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        })
    me = client.get("/auth/me")
    refreshed = client.post("/auth/refresh")
    logged_out = client.post("/auth/logout")
    unauthorized = client.get("/auth/me")
    app.dependency_overrides.clear()

    assert login.status_code == 200
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "traveler@example.com"
    assert refreshed.status_code == 200
    assert logged_out.status_code == 200
    assert unauthorized.status_code == 401


def test_duplicate_signup_and_wrong_login_are_rejected(db_session):
    client = make_client(db_session)
    first = client.post("/auth/signup", json=signup_payload())
    duplicate = client.post("/auth/signup", json=signup_payload())
    wrong_login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "wrong-pass",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        })
    app.dependency_overrides.clear()

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert wrong_login.status_code == 401


def test_forgot_and_reset_password(db_session, monkeypatch):
    client = make_client(db_session)
    sent: list[tuple[str, str, str, str]] = []

    class FakeProvider:
        provider_name = "fake"

        def send_email(self, to_email: str, subject: str, html_body: str, text_body: str, **kwargs) -> None:
            sent.append((to_email, subject, html_body, text_body))

    monkeypatch.setattr("app.auth.service.build_email_provider", lambda: FakeProvider())
    monkeypatch.setattr(settings, "app_name", "Farelin")
    monkeypatch.setattr(settings, "frontend_url", "https://farelin.com")
    client.post("/auth/signup", json=signup_payload())
    forgot = client.post("/auth/forgot-password", json={"email": "traveler@example.com",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        })
    token_row = db_session.query(PasswordResetTokenDB).one()
    reset_link = sent[0][3]
    raw_token = reset_link.rsplit("token=", 1)[1]
    reset = client.post("/auth/reset-password", json={"token": raw_token, "newPassword": "New-strong-pass-123!"})
    old_login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "Strong-pass-123!",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        })
    new_login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "New-strong-pass-123!",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        })
    app.dependency_overrides.clear()

    assert forgot.status_code == 200
    assert sent[0][1] == "Reset your Farelin password"
    assert "https://farelin.com/reset-password?token=" in sent[0][3]
    assert token_row.used_at is not None
    assert reset.status_code == 200
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_account_saved_searches_are_owned_by_current_user(db_session):
    client = make_client(db_session)
    client.post("/auth/signup", json=signup_payload())

    created = client.post("/me/saved-searches", json=saved_search_payload())
    listed = client.get("/me/saved-searches")
    row = db_session.get(SavedSearchDB, created.json()["id"])
    user = db_session.query(UserDB).filter(UserDB.email == "traveler@example.com").one()
    deleted = client.delete(f"/me/saved-searches/{created.json()['id']}")
    app.dependency_overrides.clear()

    assert created.status_code == 200
    assert created.json()["email"] == "traveler@example.com"
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert row.user_id == user.id
    assert deleted.status_code == 200
    assert row.is_active is False


def test_account_dashboard_usage_and_saved_search_edit_flow(db_session):
    client = make_client(db_session)
    client.post("/auth/signup", json=signup_payload())
    created = client.post("/me/saved-searches", json=saved_search_payload())
    saved_id = created.json()["id"]

    usage = client.get("/me/usage")
    dashboard = client.get("/me/dashboard")
    patched = client.patch(f"/me/saved-searches/{saved_id}", json={"name": "Updated alert", "maxBudget": 260})
    paused = client.post(f"/me/saved-searches/{saved_id}/pause")
    resumed = client.post(f"/me/saved-searches/{saved_id}/resume")
    app.dependency_overrides.clear()

    assert usage.status_code == 200
    assert dashboard.status_code == 200
    assert dashboard.json()["savedSearchSummary"]["total"] == 1
    assert patched.status_code == 200
    assert patched.json()["name"] == "Updated alert"
    assert patched.json()["maxBudget"] == 260
    assert paused.status_code == 200
    assert paused.json()["isActive"] is False
    assert resumed.status_code == 200
    assert resumed.json()["isActive"] is True


def test_account_watch_insights_include_history_and_respect_price_drop_baseline(db_session):
    client = make_client(db_session)
    client.post("/auth/signup", json=signup_payload())
    user = db_session.query(UserDB).filter(UserDB.email == "traveler@example.com").one()
    db_session.add(
        UserTravelProfileDB(
            user_id=user.id,
            home_location="Vienna, Austria",
            origin_airports=["VIE"],
            alert_trigger_mode="price_drop",
        )
    )
    db_session.commit()
    created = client.post(
        "/me/saved-searches",
        json=saved_search_payload(startDate="2026-07-01", endDate="2026-07-31", maxBudget=180),
    )
    saved_id = created.json()["id"]

    first_run = client.post(f"/me/saved-searches/{saved_id}/run")
    insights = client.get(f"/me/saved-searches/{saved_id}/insights")
    app.dependency_overrides.clear()

    assert first_run.status_code == 200
    assert first_run.json()["resultCount"] > 0
    assert first_run.json()["notificationSent"] is False
    assert insights.status_code == 200
    assert insights.json()["alertTriggerMode"] == "price_drop"
    assert insights.json()["totalChecks"] == 1
    assert len(insights.json()["history"]) == 1
    assert insights.json()["currentBestPrice"] is not None


def test_account_watch_insights_are_private(db_session):
    client = make_client(db_session)
    client.post("/auth/signup", json=signup_payload(email="owner@example.com"))
    created = client.post("/me/saved-searches", json=saved_search_payload())
    saved_id = created.json()["id"]
    client.post("/auth/logout")
    client.post("/auth/signup", json=signup_payload(email="other@example.com"))

    response = client.get(f"/me/saved-searches/{saved_id}/insights")
    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_account_saved_searches_require_login(db_session):
    client = make_client(db_session)

    response = client.get("/me/saved-searches")
    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_oauth_login_creates_user_with_unusable_password_and_provider_link(db_session):
    profile = OAuthProfile(
        provider="google",
        provider_user_id="google-sub-123",
        email="oauth@example.com",
        email_verified=True,
        display_name="OAuth Traveler",
    )

    user, access_token, refresh_token = AuthService(db_session).login_with_oauth(
        profile,
        oauth_state=OAuthState(
            intent="signup",
            terms_version=CURRENT_TERMS_VERSION,
            privacy_version=CURRENT_PRIVACY_VERSION,
        ),
    )
    account = db_session.query(UserOAuthAccountDB).one()

    assert user.email == "oauth@example.com"
    assert user.is_verified is True
    assert user.password_hash.startswith("oauth_unusable$")
    assert access_token
    assert refresh_token
    assert account.user_id == user.id
    assert account.provider == "google"
    assert account.provider_user_id == "google-sub-123"


def test_oauth_callback_sets_auth_cookies(db_session, monkeypatch):
    client = make_client(db_session)
    state = generate_oauth_state("signup", CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION)

    async def fake_exchange(provider, code):
        return OAuthProfile(
            provider=provider,
            provider_user_id="provider-sub-123",
            email="oauth@example.com",
            email_verified=True,
            display_name="OAuth Traveler",
        )

    monkeypatch.setattr("app.auth.routes.exchange_code_for_profile", fake_exchange)
    client.cookies.set(OAUTH_STATE_COOKIE_NAME, state)

    response = client.get(f"/auth/oauth/google/callback?code=test-code&state={state}", follow_redirects=False)
    app.dependency_overrides.clear()

    assert response.status_code == 302
    set_cookie = response.headers.get("set-cookie", "")
    assert ACCESS_COOKIE_NAME in set_cookie
    assert REFRESH_COOKIE_NAME in set_cookie


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_verified_oauth_email_may_link_a_matching_existing_account(db_session, provider):
    existing, _, _ = AuthService(db_session).signup(
        type("Signup", (), {
            "email": f"{provider}@example.com",
            "password": "Strong-pass-123!",
            "displayName": "Existing",
            "acceptedTermsVersion": CURRENT_TERMS_VERSION,
            "acknowledgedPrivacyVersion": CURRENT_PRIVACY_VERSION,
        })()
    )
    profile = OAuthProfile(
        provider=provider,
        provider_user_id=f"{provider}-verified-sub",
        email=existing.email,
        email_verified=True,
    )

    linked, _, _ = AuthService(db_session).login_with_oauth(profile)

    assert linked.id == existing.id
    assert db_session.query(UserOAuthAccountDB).filter_by(user_id=existing.id).count() == 1


def test_unverified_oauth_email_cannot_link_or_open_a_session_for_existing_user(db_session):
    from app.auth.security import hash_password

    existing = UserDB(
        id="existing-user",
        email="victim@example.com",
        password_hash=hash_password("Strong-pass-123!"),
        is_active=True,
        is_verified=True,
    )
    db_session.add(existing)
    db_session.commit()
    profile = OAuthProfile(
        provider="google",
        provider_user_id="attacker-sub",
        email="victim@example.com",
        email_verified=False,
    )

    with pytest.raises(AuthError):
        AuthService(db_session).login_with_oauth(profile)

    assert db_session.query(UserOAuthAccountDB).count() == 0
    assert len(existing.refresh_sessions) == 0


def test_existing_provider_subject_can_log_in_even_if_email_claim_is_not_repeated_as_verified(db_session):
    from app.auth.security import unusable_password_hash

    user = UserDB(
        id="provider-user",
        email="provider@example.com",
        password_hash=unusable_password_hash(),
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserOAuthAccountDB(
        id="provider-link",
        user_id=user.id,
        provider="google",
        provider_user_id="known-sub",
        email=user.email,
    ))
    db_session.commit()

    logged_in, access, refresh = AuthService(db_session).login_with_oauth(OAuthProfile(
        provider="google",
        provider_user_id="known-sub",
        email=user.email,
        email_verified=False,
    ))

    assert logged_in.id == user.id
    assert access and refresh


def test_oauth_login_does_not_silently_create_a_new_account(db_session, monkeypatch):
    client = make_client(db_session)
    state = generate_oauth_state("login")

    async def fake_exchange(provider, code):
        return OAuthProfile(provider=provider, provider_user_id="new-sub", email="new@example.com", email_verified=True)

    monkeypatch.setattr("app.auth.routes.exchange_code_for_profile", fake_exchange)
    client.cookies.set(OAUTH_STATE_COOKIE_NAME, state)
    response = client.get(f"/auth/oauth/google/callback?code=x&state={state}", follow_redirects=False)

    assert response.status_code == 302
    assert "oauth_signup_required" in response.headers["location"]
    assert db_session.query(UserDB).filter_by(email="new@example.com").count() == 0
    assert ACCESS_COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_oauth_callback_requires_the_browser_state_cookie(db_session, monkeypatch):
    client = make_client(db_session)
    state = generate_oauth_state("login")

    async def should_not_exchange(provider, code):
        raise AssertionError("provider exchange must not run without the state cookie")

    monkeypatch.setattr("app.auth.routes.exchange_code_for_profile", should_not_exchange)
    response = client.get(f"/auth/oauth/google/callback?code=x&state={state}", follow_redirects=False)

    assert response.status_code == 302
    assert "oauth_failed" in response.headers["location"]


def test_apple_oauth_state_cookie_supports_cross_site_form_post(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "apple_oauth_client_id", "com.example.farelin")

    response = client.get("/auth/oauth/apple/start?intent=login", follow_redirects=False)

    assert response.status_code == 302
    cookie = response.headers["set-cookie"].lower()
    assert "triplet_oauth_state=" in cookie
    assert "samesite=none" in cookie
    assert "secure" in cookie


def test_oauth_signup_rejects_noncanonical_legal_versions():
    response = TestClient(app).get(
        "/auth/oauth/google/start?intent=signup&termsVersion=old&privacyVersion=old",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "current Terms" in response.json()["detail"]


def test_oauth_signup_records_current_legal_acceptance(db_session, monkeypatch):
    client = make_client(db_session)
    state = generate_oauth_state("signup", CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION)

    async def fake_exchange(provider, code):
        return OAuthProfile(provider=provider, provider_user_id="legal-sub", email="legal-oauth@example.com", email_verified=True)

    monkeypatch.setattr("app.auth.routes.exchange_code_for_profile", fake_exchange)
    client.cookies.set(OAUTH_STATE_COOKIE_NAME, state)
    response = client.get(f"/auth/oauth/google/callback?code=x&state={state}", follow_redirects=False)
    user = db_session.query(UserDB).filter_by(email="legal-oauth@example.com").one()

    assert response.status_code == 302
    assert user.terms_version == CURRENT_TERMS_VERSION
    assert user.privacy_version == CURRENT_PRIVACY_VERSION
    assert user.terms_accepted_at is not None


# --- How an account actually signs in --------------------------------------

def test_an_email_account_reports_that_it_has_a_password(db_session):
    client = make_client(db_session)
    response = client.post("/auth/signup", json=signup_payload())
    app.dependency_overrides.clear()

    body = response.json()["user"]
    assert body["hasPassword"] is True
    assert body["connectedProviders"] == []


def test_a_provider_account_reports_that_it_has_none(db_session):
    """The account page used to ask such a user for a "current password" that
    had never existed, with no explanation of why it could not work."""
    from uuid import uuid4

    from app.auth.security import unusable_password_hash
    from app.auth.service import auth_user_response
    from app.db.models import UserDB, UserOAuthAccountDB

    user = UserDB(
        id=str(uuid4()),
        email="oauth@example.com",
        password_hash=unusable_password_hash(),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserOAuthAccountDB(
            id=str(uuid4()), user_id=user.id, provider="google", provider_user_id="g-1"
        )
    )
    db_session.commit()
    db_session.refresh(user)

    body = auth_user_response(user)

    assert body.hasPassword is False
    assert body.connectedProviders == ["google"]


def test_a_provider_account_that_later_set_a_password_reports_both(db_session):
    """Setting a password through the emailed reset flow is allowed, and the
    interface should then offer changing it rather than the provider notice."""
    from uuid import uuid4

    from app.auth.security import hash_password
    from app.auth.service import auth_user_response
    from app.db.models import UserDB, UserOAuthAccountDB

    user = UserDB(
        id=str(uuid4()),
        email="both@example.com",
        password_hash=hash_password("Str0ng-pass!x"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserOAuthAccountDB(
            id=str(uuid4()), user_id=user.id, provider="google", provider_user_id="g-2"
        )
    )
    db_session.commit()
    db_session.refresh(user)

    body = auth_user_response(user)

    assert body.hasPassword is True
    assert body.connectedProviders == ["google"]


def test_an_unusable_password_marker_never_counts_as_a_password():
    from app.auth.security import has_usable_password, unusable_password_hash

    class Row:
        password_hash = unusable_password_hash()

    assert has_usable_password(Row()) is False


# --- Legal acceptance is recorded, not assumed --------------------------------

def test_signup_records_which_versions_were_accepted(db_session):
    """"They must have accepted, the form required it" is not a record.

    If anyone ever asks what a given account agreed to, the answer has to come
    from a row, not from an argument about the UI.
    """
    client = make_client(db_session)
    client.post("/auth/signup", json=signup_payload(email="legal-ok@example.com"))

    user = db_session.query(UserDB).filter(UserDB.email == "legal-ok@example.com").one()
    assert user.terms_version == CURRENT_TERMS_VERSION
    assert user.privacy_version == CURRENT_PRIVACY_VERSION
    assert user.terms_accepted_at is not None


def test_signup_without_acceptance_is_refused(db_session):
    client = make_client(db_session)
    payload = signup_payload(email="legal-missing@example.com")
    payload.pop("acceptedTermsVersion", None)
    payload.pop("acknowledgedPrivacyVersion", None)

    response = client.post("/auth/signup", json=payload)

    assert response.status_code == 400
    assert "Terms" in response.json()["detail"]


def test_a_version_that_was_never_published_is_refused(db_session):
    """The client does not get to decide what it accepted.

    Recording acceptance of a document that never existed would be worse than
    recording nothing at all.
    """
    client = make_client(db_session)
    response = client.post(
        "/auth/signup",
        json=signup_payload(
            email="legal-forged@example.com",
            acceptedTermsVersion="1999-01-01",
        ),
    )

    assert response.status_code == 400
    assert db_session.query(UserDB).filter(UserDB.email == "legal-forged@example.com").count() == 0


def test_a_stale_privacy_version_is_refused(db_session):
    client = make_client(db_session)
    response = client.post(
        "/auth/signup",
        json=signup_payload(
            email="legal-stale@example.com",
            acknowledgedPrivacyVersion="2020-01-01",
        ),
    )

    assert response.status_code == 400
