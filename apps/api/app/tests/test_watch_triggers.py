"""What makes a watch worth an email.

The runner has always implemented four triggers, but the choice lived on the
user's travel profile — so it applied to every watch an account had, and you
could not follow one route for any fare at all while following another only for
an unusually cheap one. Anonymous watches could not choose at all.

The behaviour that must not change: a watch that never chose keeps behaving
exactly as it did.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.alerts.service import SavedSearchService
from app.auth.security import hash_password
from app.config import settings
from app.db.models import AlertRunDB, SavedSearchDB, UserDB, UserTravelProfileDB


def make_watch(db_session, **overrides) -> SavedSearchDB:
    values = dict(
        id=str(uuid4()),
        email="traveller@example.com",
        origin_airports=["VIE"],
        start_date=datetime(2026, 10, 1).date(),
        end_date=datetime(2026, 11, 30).date(),
        min_trip_length_days=4,
        max_trip_length_days=8,
        max_budget=400.0,
        max_ground_transfer_hours=4.0,
        trip_style="one city",
        frequency="daily",
        is_active=True,
        manage_token_hash="h",
        unsubscribe_token_hash="h",
        email_verified_at=datetime.utcnow(),
    )
    values.update(overrides)
    row = SavedSearchDB(**values)
    db_session.add(row)
    db_session.commit()
    return row


def make_user_with_profile(db_session, trigger_mode: str) -> UserDB:
    user = UserDB(
        id=str(uuid4()),
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("Str0ng-pass!x"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTravelProfileDB(
            user_id=user.id,
            home_location="Vienna",
            origin_airports=["VIE"],
            alert_trigger_mode=trigger_mode,
        )
    )
    db_session.commit()
    return user


# --- Nothing changes for a watch that never chose ---------------------------

def test_a_watch_without_a_trigger_behaves_as_it_always_did(db_session):
    """The migration leaves existing rows NULL rather than backfilling a choice
    nobody made."""
    row = make_watch(db_session, trigger_mode=None)

    assert SavedSearchService(db_session)._alert_trigger_mode(row) == "any"


def test_an_account_preference_still_applies_when_the_watch_has_none(db_session):
    user = make_user_with_profile(db_session, "below_budget")
    row = make_watch(db_session, user_id=user.id, trigger_mode=None)

    assert SavedSearchService(db_session)._alert_trigger_mode(row) == "below_budget"


# --- The watch's own choice wins -------------------------------------------

def test_a_watch_overrides_the_account_preference(db_session):
    """The point of the phase: two watches on one account can differ."""
    user = make_user_with_profile(db_session, "below_budget")
    broad = make_watch(db_session, user_id=user.id, trigger_mode="any")
    picky = make_watch(db_session, user_id=user.id, trigger_mode="route_deal")

    service = SavedSearchService(db_session)
    assert service._alert_trigger_mode(broad) == "any"
    assert service._alert_trigger_mode(picky) == "route_deal"


def test_an_anonymous_watch_can_choose_a_trigger(db_session):
    """Anonymous watches were previously stuck on "any" with no way to say
    otherwise, because the setting only existed on an account profile."""
    row = make_watch(db_session, user_id=None, trigger_mode="below_budget")

    assert SavedSearchService(db_session)._alert_trigger_mode(row) == "below_budget"


# --- Each trigger does what it says ----------------------------------------

def test_below_budget_stays_silent_above_the_ceiling(db_session):
    row = make_watch(db_session, trigger_mode="below_budget", max_budget=300.0)
    service = SavedSearchService(db_session)

    assert service._should_notify(row, 350.0) is False
    assert service._should_notify(row, 250.0) is True


def test_below_budget_does_not_repeat_a_price_it_already_sent(db_session):
    row = make_watch(db_session, trigger_mode="below_budget", max_budget=300.0,
                     last_best_price=250.0)

    assert SavedSearchService(db_session)._should_notify(row, 250.0) is False


def test_price_drop_needs_a_meaningful_fall(db_session):
    """A euro off is not news."""
    row = make_watch(db_session, trigger_mode="price_drop", last_best_price=200.0)
    service = SavedSearchService(db_session)

    assert service._should_notify(row, 199.0) is False
    assert service._should_notify(row, 150.0) is True


def test_price_drop_says_nothing_until_it_has_something_to_compare(db_session):
    row = make_watch(db_session, trigger_mode="price_drop", last_best_price=None)

    assert SavedSearchService(db_session)._should_notify(row, 100.0) is False


def test_route_deal_measures_against_what_this_route_usually_costs(db_session):
    row = make_watch(db_session, trigger_mode="route_deal", max_budget=400.0)
    for price in (300.0, 320.0, 310.0):
        db_session.add(
            AlertRunDB(id=str(uuid4()), saved_search_id=row.id, status="success",
                       result_count=1, best_price=price)
        )
    db_session.commit()
    service = SavedSearchService(db_session)

    # Average is 310; 85% of that is 263.50.
    assert service._should_notify(row, 300.0) is False
    assert service._should_notify(row, 240.0) is True


def test_route_deal_falls_back_to_the_budget_before_it_has_history(db_session):
    row = make_watch(db_session, trigger_mode="route_deal", max_budget=400.0)
    service = SavedSearchService(db_session)

    assert service._should_notify(row, 350.0) is False
    assert service._should_notify(row, 300.0) is True


# --- What triggers is separate from how often ------------------------------

def test_the_cooldown_applies_whatever_the_trigger(db_session):
    """Trigger and cadence are different questions, and a keen trigger must not
    become a way around the send cooldown."""
    just_sent = datetime.utcnow() - timedelta(minutes=5)
    for mode in ("any", "below_budget", "route_deal", "price_drop"):
        row = make_watch(db_session, trigger_mode=mode, last_notified_at=just_sent,
                         max_budget=400.0, last_best_price=300.0)

        assert SavedSearchService(db_session)._should_notify(row, 10.0) is False, mode


def test_frequency_and_trigger_are_stored_independently(db_session):
    row = make_watch(db_session, trigger_mode="route_deal", frequency="weekly")

    db_session.refresh(row)
    assert row.trigger_mode == "route_deal"
    assert row.frequency == "weekly"


# --- Only what the runner implements ---------------------------------------

def test_the_api_refuses_a_trigger_the_runner_cannot_honour(db_session):
    """Offering a choice the backend ignores would be worse than no choice."""
    from app.alerts.schemas import CreateSavedSearchRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateSavedSearchRequest(
            email="a@example.com", originAirports=["VIE"],
            startDate=datetime(2026, 10, 1).date(), endDate=datetime(2026, 11, 30).date(),
            minTripLengthDays=4, maxTripLengthDays=8, maxBudget=400,
            maxGroundTransferHours=4, tripStyle="one city",
            triggerMode="direct_flight_appears",
        )
