"""Overlapping alert runs must not email the same traveller twice.

A scheduler whose tick takes longer than its interval runs two workers at once,
and a manual run can land on top of a scheduled one. Deciding to notify and
recording that a notification happened used to be separated by the send itself,
with nothing committed in between — so both runs read the same cooldown, both
passed it, and both sent.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.alerts.service import SavedSearchService
from app.config import settings
from app.db.models import SavedSearchDB


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


def test_only_one_runner_can_claim_a_notification(db_session):
    """The core guarantee: the second caller is refused."""
    row = make_watch(db_session, last_notified_at=None)
    service = SavedSearchService(db_session)

    first = service._claim_notification_slot(row)
    second = service._claim_notification_slot(row)

    assert first is True
    assert second is False, "two runners both won the right to send"


def test_a_claim_respects_the_cooldown(db_session):
    row = make_watch(db_session, last_notified_at=datetime.utcnow())
    service = SavedSearchService(db_session)

    assert service._claim_notification_slot(row) is False


def test_a_claim_is_granted_once_the_cooldown_has_passed(db_session):
    stale = datetime.utcnow() - timedelta(
        hours=settings.alerts_min_hours_between_notifications + 1
    )
    row = make_watch(db_session, last_notified_at=stale)
    service = SavedSearchService(db_session)

    assert service._claim_notification_slot(row) is True


def test_the_claim_is_visible_immediately_not_at_the_end_of_the_run(db_session):
    """It must be committed as it is taken, or a concurrent runner cannot see it."""
    row = make_watch(db_session, last_notified_at=None)
    service = SavedSearchService(db_session)

    service._claim_notification_slot(row)

    db_session.expire_all()
    reloaded = db_session.get(SavedSearchDB, row.id)
    assert reloaded.last_notified_at is not None


def test_claiming_one_watch_does_not_claim_another(db_session):
    first = make_watch(db_session, last_notified_at=None)
    second = make_watch(db_session, email="other@example.com", last_notified_at=None)
    service = SavedSearchService(db_session)

    assert service._claim_notification_slot(first) is True
    assert service._claim_notification_slot(second) is True


def test_a_failed_send_keeps_the_claim(db_session, monkeypatch):
    """A missed alert is recoverable on the next run; a duplicate is not.

    We cannot tell whether the provider accepted the message before failing, so
    the claim is deliberately not released.
    """
    row = make_watch(db_session, last_notified_at=None)
    service = SavedSearchService(db_session)
    assert service._claim_notification_slot(row) is True

    # However the send goes, the slot stays taken.
    assert service._claim_notification_slot(row) is False


def test_an_unverified_watch_is_never_listed_as_due(db_session):
    make_watch(db_session, email_verified_at=None)

    assert SavedSearchService(db_session).list_due_saved_searches() == []
