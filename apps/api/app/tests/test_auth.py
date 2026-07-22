from fastapi.testclient import TestClient

from app.auth.oauth import OAUTH_STATE_COOKIE_NAME, OAuthProfile, generate_oauth_state
from app.auth.security import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.auth.service import AuthService
from app.database import get_db
from app.db.models import PasswordResetTokenDB, SavedSearchDB, UserDB, UserOAuthAccountDB
from app.main import app


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def signup_payload(**overrides):
    payload = {
        "email": "traveler@example.com",
        "password": "Strong-pass-123!",
        "displayName": "Traveler",
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
    assert user.password_hash.startswith("pbkdf2_sha256$")


def test_signup_rejects_weak_password(db_session):
    client = make_client(db_session)

    response = client.post("/auth/signup", json=signup_payload(password="short"))
    app.dependency_overrides.clear()

    assert response.status_code == 400


def test_login_me_refresh_and_logout_flow(db_session):
    client = make_client(db_session)
    client.post("/auth/signup", json=signup_payload())
    client.post("/auth/logout")

    login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "Strong-pass-123!"})
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
    wrong_login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "wrong-pass"})
    app.dependency_overrides.clear()

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert wrong_login.status_code == 401


def test_forgot_and_reset_password(db_session, monkeypatch):
    client = make_client(db_session)
    sent: list[tuple[str, str, str, str]] = []

    class FakeProvider:
        provider_name = "fake"

        def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> None:
            sent.append((to_email, subject, html_body, text_body))

    monkeypatch.setattr("app.auth.service.build_email_provider", lambda: FakeProvider())
    client.post("/auth/signup", json=signup_payload())
    forgot = client.post("/auth/forgot-password", json={"email": "traveler@example.com"})
    token_row = db_session.query(PasswordResetTokenDB).one()
    reset_link = sent[0][3]
    raw_token = reset_link.rsplit("token=", 1)[1]
    reset = client.post("/auth/reset-password", json={"token": raw_token, "newPassword": "New-strong-pass-123!"})
    old_login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "Strong-pass-123!"})
    new_login = client.post("/auth/login", json={"email": "traveler@example.com", "password": "New-strong-pass-123!"})
    app.dependency_overrides.clear()

    assert forgot.status_code == 200
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

    user, access_token, refresh_token = AuthService(db_session).login_with_oauth(profile)
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
    state = generate_oauth_state()

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
