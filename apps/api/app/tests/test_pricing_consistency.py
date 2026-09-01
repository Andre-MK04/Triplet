"""What the pricing page is allowed to claim.

Plan limits were described in three places: the settings that enforce them, the
feature strings the API returned, and constants in the pricing page. All three
agreed, which is the dangerous kind of duplication — raising a limit made the
pricing page quietly wrong rather than breaking anything.
"""

import pytest

from app.billing.service import available_plans, yearly_savings_percent
from app.config import settings


def plan(name: str):
    return next(p for p in available_plans() if p.plan == name)


# --- Features follow the limits that are actually enforced -----------------

def test_free_features_follow_the_configured_limits(monkeypatch):
    monkeypatch.setattr(settings, "triplet_free_ai_searches_per_month", 7)
    monkeypatch.setattr(settings, "triplet_free_saved_search_limit", 4)
    monkeypatch.setattr(settings, "triplet_free_max_origin_airports", 5)

    features = plan("free").features

    assert "7 AI searches/month" in features
    assert "4 saved watches" in features
    assert "5 origin airports" in features


def test_pro_features_follow_the_configured_limits(monkeypatch):
    monkeypatch.setattr(settings, "triplet_pro_ai_searches_per_month", 250)
    monkeypatch.setattr(settings, "triplet_pro_saved_search_limit", 25)

    features = plan("pro").features

    assert "250 AI searches/month" in features
    assert "25 saved watches" in features


def test_raising_a_limit_changes_what_the_page_says(monkeypatch):
    """The regression this file exists for."""
    before = plan("pro").features
    monkeypatch.setattr(settings, "triplet_pro_ai_searches_per_month", 999)

    assert plan("pro").features != before
    assert "999 AI searches/month" in plan("pro").features


def test_a_single_watch_is_described_in_the_singular(monkeypatch):
    monkeypatch.setattr(settings, "triplet_free_saved_search_limit", 1)

    assert "1 saved watch" in plan("free").features


def test_fare_check_cadence_follows_the_allowed_frequencies(monkeypatch):
    monkeypatch.setattr(settings, "triplet_free_alert_frequencies", "weekly")
    assert "Weekly fare checks" in plan("free").features

    monkeypatch.setattr(settings, "triplet_free_alert_frequencies", "daily,weekly")
    assert "Daily fare checks" in plan("free").features


def test_the_trial_is_described_as_a_total_not_a_monthly_rate(monkeypatch):
    """A trial cap is a total across its window; calling it "per month" would
    promise a renewal that never comes."""
    monkeypatch.setattr(settings, "triplet_trial_ai_searches_total", 15)

    features = plan("trial").features

    assert "15 AI searches total" in features
    assert not any("/month" in feature for feature in features)


def test_the_trial_plan_is_offered_at_all():
    """The page described a trial the API never returned, so its details could
    not be checked against anything."""
    assert plan("trial") is not None
    assert plan("trial").priceLabel == "€0"


def test_free_does_not_advertise_what_it_cannot_do():
    features = plan("free").features

    assert not any("Open-jaw" in feature for feature in features)


# --- The yearly saving is calculated, never asserted -----------------------

def test_the_saving_is_computed_from_the_real_prices(monkeypatch):
    monkeypatch.setattr(settings, "triplet_pro_price_monthly_amount", 10.0)
    monkeypatch.setattr(settings, "triplet_pro_price_yearly_amount", 60.0)

    # 120 a year monthly, 60 yearly: half.
    assert yearly_savings_percent() == 50


def test_no_saving_is_quoted_when_the_prices_are_unknown(monkeypatch):
    """Better to say nothing than to repeat a number nobody calculated."""
    monkeypatch.setattr(settings, "triplet_pro_price_yearly_amount", None)

    assert yearly_savings_percent() is None


def test_no_saving_is_quoted_when_yearly_is_not_actually_cheaper(monkeypatch):
    monkeypatch.setattr(settings, "triplet_pro_price_monthly_amount", 5.0)
    monkeypatch.setattr(settings, "triplet_pro_price_yearly_amount", 60.0)

    assert yearly_savings_percent() is None


def test_the_default_prices_produce_the_real_figure(monkeypatch):
    """6.99 x 12 = 83.88 against 49 is 42%, not the "~40%" the page used to
    state as fixed text."""
    monkeypatch.setattr(settings, "triplet_pro_price_monthly_amount", 6.99)
    monkeypatch.setattr(settings, "triplet_pro_price_yearly_amount", 49.0)

    assert yearly_savings_percent() == 42


# --- The page must know whether it can actually sell anything --------------

def test_plans_report_whether_checkout_can_complete(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(settings, "billing_enabled", False)
    with TestClient(app) as client:
        body = client.get("/billing/plans").json()
    app.dependency_overrides.clear()

    assert body["billingEnabled"] is False
    assert {p["plan"] for p in body["plans"]} == {"free", "trial", "pro"}
