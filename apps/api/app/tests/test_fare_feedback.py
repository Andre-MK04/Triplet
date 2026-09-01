"""What travellers report about fares they went and checked.

Triplet shows observed prices and says so, but has never been able to size that
caveat. This is how it learns to. Two properties matter more than the
arithmetic: the record says nothing about who answered, and nothing is
reportable from a handful of answers.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.db.models import FareFeedbackDB
from app.main import app
from app.pricing.reliability import (
    MIN_SAMPLE_FOR_REPORTING,
    overall_reliability,
    record_feedback,
    reliability_by_age_bucket,
    reliability_by_fare_kind,
    reliability_for_route,
)
from app.security import reset_rate_limits


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


def feedback(db, check_id: str, **overrides) -> bool:
    values = dict(
        origin="VIE", destination="BCN", trip_type="same_city",
        fare_kind="cached_return", fare_age_bucket="fresh",
        shown_price=120.0, response="matched", provider="travelpayouts",
    )
    values.update(overrides)
    return record_feedback(db, check_id=check_id, **values)


def payload(**overrides) -> dict:
    body = {
        "checkId": "check-00000001",
        "origin": "VIE",
        "destination": "BCN",
        "tripType": "same_city",
        "fareKind": "cached_return",
        "fareAgeBucket": "fresh",
        "shownPrice": 120.0,
        "response": "matched",
        "currency": "EUR",
        "provider": "travelpayouts",
    }
    body.update(overrides)
    return body


# --- Privacy ---------------------------------------------------------------

def test_a_report_records_nothing_about_the_person(db_session, client):
    """The question is about fares. Nothing here should identify a traveller."""
    client.post("/fare-feedback", json=payload())

    row = db_session.query(FareFeedbackDB).one()
    columns = {column.name for column in row.__table__.columns}
    assert "user_id" not in columns
    assert "ip_address" not in columns
    assert "email" not in columns
    assert "session_id" not in columns


def test_the_schema_refuses_unexpected_fields(client):
    """A closed schema, so a client cannot smuggle anything into the record."""
    response = client.post("/fare-feedback", json={**payload(), "userEmail": "a@b.com"})

    assert response.status_code == 422


# --- One answer per check --------------------------------------------------

def test_one_check_yields_one_answer(db_session):
    assert feedback(db_session, "check-a") is True
    assert feedback(db_session, "check-a", response="much_higher") is False

    assert db_session.query(FareFeedbackDB).count() == 1


def test_a_repeated_submission_is_accepted_without_double_counting(client, db_session):
    first = client.post("/fare-feedback", json=payload())
    second = client.post("/fare-feedback", json=payload())

    assert first.json()["recorded"] is True
    # Not an error: the client should stop asking either way.
    assert second.status_code == 200
    assert second.json()["recorded"] is False
    assert db_session.query(FareFeedbackDB).count() == 1


def test_different_checks_are_recorded_separately(db_session):
    feedback(db_session, "check-a")
    feedback(db_session, "check-b")

    assert db_session.query(FareFeedbackDB).count() == 2


# --- Validation ------------------------------------------------------------

@pytest.mark.parametrize("bad", ["cheaper", "", "MATCHED", "unknown"])
def test_an_unknown_response_is_refused(client, bad):
    assert client.post("/fare-feedback", json=payload(response=bad)).status_code in (400, 422)


def test_an_unknown_age_bucket_is_refused(client):
    assert client.post("/fare-feedback", json=payload(fareAgeBucket="ancient")).status_code in (400, 422)


def test_a_nonsense_price_is_refused(client):
    assert client.post("/fare-feedback", json=payload(shownPrice=-5)).status_code == 422


def test_the_endpoint_is_rate_limited(client):
    for index in range(settings.rate_limit_cheap_per_window):
        client.post("/fare-feedback", json=payload(checkId=f"check-{index:08d}"))

    assert client.post("/fare-feedback", json=payload(checkId="check-final")).status_code == 429


# --- Aggregates ------------------------------------------------------------

def test_nothing_is_reportable_from_a_handful_of_answers(db_session):
    """The temptation this guards against: a confident claim from four reports."""
    for index in range(4):
        feedback(db_session, f"check-{index}")

    summary = overall_reliability(db_session)

    assert summary.sampleCount == 4
    assert summary.isReportable is False


def test_a_group_becomes_reportable_at_the_threshold(db_session):
    for index in range(MIN_SAMPLE_FOR_REPORTING):
        feedback(db_session, f"check-{index}")

    summary = overall_reliability(db_session)

    assert summary.sampleCount == MIN_SAMPLE_FOR_REPORTING
    assert summary.isReportable is True


def test_a_small_move_counts_as_holding_up(db_session):
    """Fares move. A little higher is the market working, not a bad observation."""
    for index in range(10):
        feedback(db_session, f"m-{index}", response="matched")
    for index in range(10):
        feedback(db_session, f"s-{index}", response="slightly_higher")

    summary = overall_reliability(db_session)

    assert summary.closeRate == 1.0
    assert summary.close_percentage == 100


def test_a_large_move_and_a_vanished_fare_do_not(db_session):
    for index in range(10):
        feedback(db_session, f"m-{index}", response="matched")
    for index in range(5):
        feedback(db_session, f"h-{index}", response="much_higher")
    for index in range(5):
        feedback(db_session, f"g-{index}", response="unavailable")

    summary = overall_reliability(db_session)

    assert summary.close_percentage == 50
    assert summary.unavailableRate == 0.25


def test_reliability_splits_by_fare_age(db_session):
    """The question the table exists to answer: do older fares hold up worse?"""
    for index in range(20):
        feedback(db_session, f"fresh-{index}", fare_age_bucket="fresh", response="matched")
    for index in range(20):
        feedback(
            db_session, f"stale-{index}", fare_age_bucket="stale",
            response="matched" if index < 8 else "much_higher",
        )

    by_bucket = {s.group: s for s in reliability_by_age_bucket(db_session)}

    assert by_bucket["fresh"].close_percentage == 100
    assert by_bucket["stale"].close_percentage == 40
    assert by_bucket["fresh"].isReportable and by_bucket["stale"].isReportable


def test_reliability_splits_by_fare_kind(db_session):
    """Whether assembled estimates really do hold up worse than observed fares."""
    for index in range(20):
        feedback(db_session, f"r-{index}", fare_kind="cached_return", response="matched")
    for index in range(20):
        feedback(
            db_session, f"e-{index}", fare_kind="estimated_multi_city",
            response="matched" if index < 10 else "much_higher",
        )

    by_kind = {s.group: s for s in reliability_by_fare_kind(db_session)}

    assert by_kind["cached_return"].close_percentage == 100
    assert by_kind["estimated_multi_city"].close_percentage == 50


def test_a_single_route_is_almost_never_reportable(db_session):
    """The most tempting label to build here, and the least defensible: the
    sample is thinnest exactly where the claim would be most specific."""
    for index in range(6):
        feedback(db_session, f"check-{index}", origin="VIE", destination="BCN")

    summary = reliability_for_route(db_session, "VIE", "BCN")

    assert summary.sampleCount == 6
    assert summary.isReportable is False


def test_routes_are_counted_separately(db_session):
    for index in range(3):
        feedback(db_session, f"bcn-{index}", destination="BCN")
    for index in range(5):
        feedback(db_session, f"pmo-{index}", destination="PMO")

    assert reliability_for_route(db_session, "VIE", "BCN").sampleCount == 3
    assert reliability_for_route(db_session, "VIE", "PMO").sampleCount == 5


def test_an_empty_table_reports_nothing_rather_than_zero_percent(db_session):
    """No data must not read as "these fares never hold up"."""
    summary = overall_reliability(db_session)

    assert summary.sampleCount == 0
    assert summary.closeRate is None
    assert summary.close_percentage is None
    assert summary.isReportable is False


def test_an_invalid_response_is_refused_at_the_service_too(db_session):
    with pytest.raises(ValueError, match="Unknown feedback response"):
        feedback(db_session, "check-x", response="cheaper")
