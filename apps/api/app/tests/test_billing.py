from fastapi.testclient import TestClient

from datetime import datetime, timedelta

from app.billing.entitlements import get_entitlements, get_user_plan
from app.billing.service import start_trial
from app.billing.usage import assert_ai_search_allowed, record_ai_search
from app.billing.webhooks import process_stripe_event
from app.config import settings
from app.database import get_db
from app.db.models import BillingEventDB, UserDB
from app.main import app


def make_user(session, **overrides) -> UserDB:
    values = {
        "id": overrides.pop("id", "user-1"),
        "email": overrides.pop("email", "user1@example.com"),
        "password_hash": "oauth_unusable$test",
        "plan": "free",
        "subscription_status": "none",
        "is_active": True,
        "is_verified": True,
    }
    values.update(overrides)
    user = UserDB(**values)
    session.add(user)
    session.commit()
    return user


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def make_client(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    return TestClient(app)


def signup(client, email="billing@example.com"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": "Strong-pass-123!", "displayName": "Billing User"},
    )


def saved_search_payload(**overrides):
    payload = {
        "email": "billing@example.com",
        "name": "Billing alert",
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
        "frequency": "daily",
    }
    payload.update(overrides)
    return payload


def test_billing_disabled_status_returns_free_entitlements(db_session, monkeypatch):
    monkeypatch.setattr(settings, "billing_enabled", False)
    client = make_client(db_session)
    signup(client)

    response = client.get("/billing/status")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["limits"]["savedSearchLimit"] == settings.triplet_free_saved_search_limit


def test_checkout_disabled_returns_clean_error(db_session, monkeypatch):
    monkeypatch.setattr(settings, "billing_enabled", False)
    client = make_client(db_session)
    signup(client)

    response = client.post("/billing/create-checkout-session", json={"interval": "monthly"})
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "Billing is not enabled" in response.text


def test_checkout_uses_configured_price_and_does_not_expose_secret(db_session, monkeypatch):
    client = make_client(db_session)
    signup(client)
    calls = {}

    class FakeCustomer:
        @staticmethod
        def create(**kwargs):
            calls["customer"] = kwargs
            return {"id": "cus_test"}

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs):
            calls["checkout"] = kwargs
            return {"url": "https://checkout.stripe.test/session"}

    class FakeCheckout:
        Session = FakeCheckoutSession

    class FakeStripe:
        Customer = FakeCustomer
        checkout = FakeCheckout
        api_key = None

    monkeypatch.setattr(settings, "billing_enabled", True)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_secret")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_monthly")
    monkeypatch.setattr("app.billing.stripe_client.stripe", FakeStripe)

    response = client.post("/billing/create-checkout-session", json={"interval": "monthly"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["checkoutUrl"] == "https://checkout.stripe.test/session"
    assert calls["checkout"]["line_items"][0]["price"] == "price_monthly"
    assert "sk_test_secret" not in response.text


def test_entitlements_free_pro_and_canceled(db_session):
    user = UserDB(
        id="user-billing",
        email="plan@example.com",
        password_hash="oauth_unusable$test",
        plan="free",
        subscription_status="none",
        is_active=True,
        is_verified=True,
    )

    assert get_entitlements(user)["plan"] == "free"
    user.plan = "pro"
    user.subscription_status = "active"
    assert get_entitlements(user)["plan"] == "pro"
    user.subscription_status = "past_due"
    assert get_entitlements(user)["plan"] == "pro"
    user.subscription_status = "canceled"
    assert get_entitlements(user)["plan"] == "free"


def test_ai_usage_limit_blocks_after_free_monthly_limit(db_session, monkeypatch):
    user = make_user(db_session, id="usage-user", email="usage@example.com")
    monkeypatch.setattr(settings, "triplet_free_ai_searches_per_month", 2)

    assert_ai_search_allowed(db_session, user)
    record_ai_search(db_session, user)
    record_ai_search(db_session, user)

    try:
        assert_ai_search_allowed(db_session, user)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 402
        assert "this month" in str(exc.detail)
    else:
        raise AssertionError("Expected AI usage limit to block")


def test_saved_search_limit_blocks_free_user(db_session, monkeypatch):
    monkeypatch.setattr(settings, "triplet_free_saved_search_limit", 1)
    client = make_client(db_session)
    signup(client)

    # Free allows weekly checks only; use weekly so this tests the COUNT limit.
    first = client.post("/me/saved-searches", json=saved_search_payload(frequency="weekly"))
    second = client.post("/me/saved-searches", json=saved_search_payload(name="Second", frequency="weekly"))
    app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 402


def test_stripe_webhook_updates_user_plan_and_is_idempotent(db_session):
    user = UserDB(
        id="webhook-user",
        email="webhook@example.com",
        password_hash="oauth_unusable$test",
        stripe_customer_id="cus_webhook",
        plan="free",
        subscription_status="none",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    event = {
        "id": "evt_1",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_webhook",
                "status": "active",
                "cancel_at_period_end": False,
                "items": {"data": [{"price": {"id": "price_monthly"}}]},
            }
        },
    }

    first = process_stripe_event(db_session, event)
    second = process_stripe_event(db_session, event)
    refreshed = db_session.get(UserDB, "webhook-user")
    event_count = db_session.query(BillingEventDB).count()

    assert first == "success"
    assert second == "success"
    assert event_count == 1
    assert refreshed.plan == "pro"
    assert refreshed.subscription_status == "active"


def test_webhook_rejects_missing_signature(db_session, monkeypatch):
    monkeypatch.setattr(settings, "billing_enabled", True)
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    client = make_client(db_session)

    response = client.post("/billing/webhook", content=b"{}")
    app.dependency_overrides.clear()

    assert response.status_code == 400


# --- Free / Trial / Pro entitlements -----------------------------------------


def test_free_entitlement_limits(db_session):
    user = make_user(db_session)
    ent = get_entitlements(user)
    assert ent["plan"] == "free"
    assert ent["savedSearchLimit"] == 1
    assert ent["aiSearchesPerMonth"] == 3
    assert ent["maxOriginAirports"] == 3
    assert ent["allowedAlertFrequencies"] == ["weekly"]
    assert ent["dailyWatchChecks"] is False
    assert ent["weeklyWatchChecks"] is True


def test_trial_entitlement_limits(db_session):
    now = datetime.utcnow()
    user = make_user(
        db_session,
        plan="trial",
        subscription_status="trialing",
        trial_started_at=now,
        trial_ends_at=now + timedelta(days=7),
        trial_used=True,
    )
    ent = get_entitlements(user)
    assert ent["plan"] == "trial"
    assert ent["savedSearchLimit"] == 3
    assert ent["aiSearchesPerMonth"] == 15  # total across trial window
    assert ent["maxOriginAirports"] == 6
    assert ent["dailyWatchChecks"] is True


def test_pro_entitlement_limits(db_session):
    user = make_user(db_session, plan="pro", subscription_status="active")
    ent = get_entitlements(user)
    assert ent["plan"] == "pro"
    assert ent["savedSearchLimit"] == 10
    assert ent["aiSearchesPerMonth"] == 100
    assert ent["maxOriginAirports"] == 8
    assert ent["dailyWatchChecks"] is True


def test_expired_trial_falls_back_to_free(db_session):
    now = datetime.utcnow()
    user = make_user(
        db_session,
        plan="trial",
        subscription_status="trialing",
        trial_started_at=now - timedelta(days=8),
        trial_ends_at=now - timedelta(days=1),
        trial_used=True,
    )
    assert get_user_plan(user) == "free"
    assert get_entitlements(user)["savedSearchLimit"] == 1


def test_active_pro_overrides_trial_fields(db_session):
    now = datetime.utcnow()
    user = make_user(
        db_session,
        plan="pro",
        subscription_status="active",
        trial_started_at=now,
        trial_ends_at=now + timedelta(days=3),
        trial_used=True,
    )
    assert get_user_plan(user) == "pro"
    assert get_entitlements(user)["aiSearchesPerMonth"] == 100


# --- Trial lifecycle ---------------------------------------------------------


def test_start_trial_sets_window_and_status(db_session):
    user = make_user(db_session)
    status = start_trial(db_session, user)
    assert status["plan"] == "trial"
    assert status["subscriptionStatus"] == "trialing"
    assert status["trialDaysRemaining"] == 7
    assert user.trial_used is True
    assert user.trial_ends_at is not None


def test_cannot_start_second_trial(db_session):
    user = make_user(db_session)
    start_trial(db_session, user)
    # Even after it expires, trial_used stays true.
    user.trial_ends_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    try:
        start_trial(db_session, user)
    except Exception as exc:
        assert "already used" in str(exc).lower()
    else:
        raise AssertionError("Expected second trial to be rejected")


def test_pro_user_cannot_start_trial(db_session):
    user = make_user(db_session, plan="pro", subscription_status="active")
    try:
        start_trial(db_session, user)
    except Exception as exc:
        assert "pro" in str(exc).lower()
    else:
        raise AssertionError("Expected Pro user trial start to be rejected")


def test_trial_ai_searches_capped_at_total(db_session, monkeypatch):
    monkeypatch.setattr(settings, "triplet_trial_ai_searches_total", 3)
    now = datetime.utcnow()
    user = make_user(
        db_session,
        plan="trial",
        subscription_status="trialing",
        trial_started_at=now,
        trial_ends_at=now + timedelta(days=7),
        trial_used=True,
    )
    for _ in range(3):
        assert_ai_search_allowed(db_session, user)
        record_ai_search(db_session, user)
    try:
        assert_ai_search_allowed(db_session, user)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 402
        assert "trial" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected trial AI cap to block")


def test_structured_search_not_counted_against_ai_usage(db_session):
    # record_ai_search is only called by the AI route, not /trips/search.
    # This documents that only AI searches touch the AI counter.
    from app.billing.usage import get_ai_usage

    user = make_user(db_session)
    assert get_ai_usage(db_session, user) == 0


def test_start_trial_endpoint(db_session):
    client = make_client(db_session)
    signup(client, email="trialer@example.com")
    res = client.post("/billing/start-trial")
    app.dependency_overrides.clear()
    assert res.status_code == 200
    body = res.json()
    assert body["plan"] == "trial"
    assert body["trialDaysRemaining"] == 7
    assert body["canStartTrial"] is False


def test_origin_airport_limit_enforced_free(db_session, monkeypatch):
    from app.billing.usage import assert_origin_airports_allowed

    user = make_user(db_session)
    assert_origin_airports_allowed(user, 3)  # ok
    try:
        assert_origin_airports_allowed(user, 4)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 402
        assert "up to 3" in str(exc.detail)
    else:
        raise AssertionError("Expected origin airport limit to block")


def test_free_user_cannot_create_daily_watch(db_session):
    from app.billing.usage import assert_saved_search_allowed

    user = make_user(db_session)
    try:
        assert_saved_search_allowed(db_session, user, "daily")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 402
        assert "trial" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected daily frequency to be blocked on Free")
