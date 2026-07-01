from fastapi.testclient import TestClient

from app.billing.entitlements import get_entitlements
from app.billing.usage import AI_SEARCH, assert_ai_search_allowed, increment_usage
from app.billing.webhooks import process_stripe_event
from app.config import settings
from app.database import get_db
from app.db.models import BillingEventDB, UserDB
from app.main import app


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


def test_ai_usage_limit_blocks_after_free_limit(db_session, monkeypatch):
    user = UserDB(
        id="usage-user",
        email="usage@example.com",
        password_hash="oauth_unusable$test",
        plan="free",
        subscription_status="none",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    monkeypatch.setattr(settings, "triplet_free_ai_searches_per_day", 2)

    assert_ai_search_allowed(db_session, user)
    increment_usage(db_session, user.id, AI_SEARCH)
    increment_usage(db_session, user.id, AI_SEARCH)

    try:
        assert_ai_search_allowed(db_session, user)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 402
    else:
        raise AssertionError("Expected AI usage limit to block")


def test_saved_search_limit_blocks_free_user(db_session, monkeypatch):
    monkeypatch.setattr(settings, "triplet_free_saved_search_limit", 1)
    client = make_client(db_session)
    signup(client)

    first = client.post("/me/saved-searches", json=saved_search_payload())
    second = client.post("/me/saved-searches", json=saved_search_payload(name="Second"))
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
