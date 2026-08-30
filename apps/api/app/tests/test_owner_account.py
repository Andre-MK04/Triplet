"""Owner accounts: the people who run and test Triplet have no plan limits.

Configured by email through TRIPLET_OWNER_EMAILS so no address is committed to
what is a public repository.
"""

import pytest
from fastapi import HTTPException

from app.billing.entitlements import (
    UNLIMITED,
    can_start_trial,
    get_entitlements,
    get_user_plan,
    is_owner_email,
)
from app.billing.usage import assert_ai_search_allowed, assert_origin_airports_allowed
from app.config import settings
from app.db.models import UserDB


@pytest.fixture()
def owner(monkeypatch, db_session):
    monkeypatch.setattr(settings, "triplet_owner_emails", "Owner@Example.com, second@example.com")
    user = UserDB(id="owner-1", email="owner@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def regular(db_session):
    user = UserDB(id="user-1", email="someone@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    return user


def test_owner_matching_ignores_case_and_padding(monkeypatch):
    monkeypatch.setattr(settings, "triplet_owner_emails", " Owner@Example.com ")

    assert is_owner_email("owner@example.com")
    assert is_owner_email("OWNER@EXAMPLE.COM")
    assert not is_owner_email("someone@example.com")
    assert not is_owner_email(None)


def test_no_owners_configured_means_nobody_is_an_owner(monkeypatch):
    monkeypatch.setattr(settings, "triplet_owner_emails", "")

    assert not is_owner_email("owner@example.com")


def test_owner_plan_lifts_every_limit(owner):
    entitlements = get_entitlements(owner)

    assert get_user_plan(owner) == "owner"
    assert entitlements["unlimited"] is True
    assert entitlements["aiSearchesPerMonth"] == UNLIMITED
    assert entitlements["savedSearchLimit"] == UNLIMITED
    assert entitlements["maxOriginAirports"] == UNLIMITED
    assert entitlements["liveProviderAccess"] is True
    assert entitlements["dailyWatchChecks"] is True


def test_owner_ai_searches_are_never_blocked(db_session, owner):
    from app.billing.usage import record_ai_search

    for _ in range(50):
        record_ai_search(db_session, owner)

    assert_ai_search_allowed(db_session, owner)  # does not raise


def test_owner_can_search_from_many_origins(owner):
    assert_origin_airports_allowed(owner, 25)  # does not raise


def test_free_account_still_hits_its_limits(db_session, regular):
    from app.billing.usage import record_ai_search

    assert get_user_plan(regular) == "free"
    assert get_entitlements(regular)["unlimited"] is False
    for _ in range(settings.triplet_free_ai_searches_per_month):
        record_ai_search(db_session, regular)

    with pytest.raises(HTTPException) as raised:
        assert_ai_search_allowed(db_session, regular)
    assert raised.value.status_code == 402


def test_owner_is_not_offered_a_trial_that_would_downgrade_them(owner):
    assert can_start_trial(owner) is False
