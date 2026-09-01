"""The homepage board.

The landing page ran a full trip search on every page view — a real provider
search, with real cost, for every visitor, crawler and uptime check. The
guarantee under test is that loading the homepage now costs one indexed read
and reaches no provider at all.

The second thing under test is honesty about time. The board is rebuilt on a
schedule; the fares in it are whatever age the provider's data is. Those are two
different clocks and the response keeps them apart.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.db.models import FeaturedDealSnapshotDB
from app.deals.featured import (
    board_is_stale,
    featured_origins,
    latest_snapshot,
    refresh_featured_deals,
)
from app.main import app
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


def plant_board(db_session, *, trips=None, generated_at=None) -> FeaturedDealSnapshotDB:
    snapshot = FeaturedDealSnapshotDB(
        generated_at=generated_at or datetime.utcnow(),
        trips=trips if trips is not None else [],
        origin_airports=["VIE", "BUD"],
        trip_count=len(trips or []),
    )
    db_session.add(snapshot)
    db_session.commit()
    return snapshot


# --- The point of the whole phase ------------------------------------------

def test_a_homepage_view_never_calls_a_flight_provider(client, db_session, monkeypatch):
    """The regression this phase exists to prevent."""
    called = []

    def explode(*args, **kwargs):
        called.append(args)
        raise AssertionError("the homepage reached a flight provider")

    monkeypatch.setattr("app.deals.featured.build_default_tool_registry", explode)
    plant_board(db_session)

    for _ in range(5):
        assert client.get("/featured-deals").status_code == 200

    assert called == []


def test_the_board_is_served_from_the_stored_snapshot(client, db_session):
    plant_board(db_session, trips=[])

    body = client.get("/featured-deals").json()

    assert body["isReady"] is True
    assert body["originAirports"] == ["VIE", "BUD"]
    assert body["generatedAt"]


def test_before_the_scheduler_has_run_the_page_is_told_so(client):
    """An empty board is not the same claim as "no cheap fares exist"."""
    body = client.get("/featured-deals").json()

    assert body["isReady"] is False
    assert body["trips"] == []


# --- Two clocks -------------------------------------------------------------

def test_the_board_reports_when_it_was_built_not_how_old_its_fares_are(client, db_session):
    """Rebuilding hourly does not make the fares in it an hour old."""
    built = datetime.utcnow() - timedelta(minutes=30)
    plant_board(db_session, generated_at=built)

    body = client.get("/featured-deals").json()

    # The board timestamp is the board's own, and is the only time the response
    # states at the top level. Fare ages travel inside each trip.
    assert body["generatedAt"].startswith(built.isoformat()[:16])
    assert "ageHours" not in body
    assert "observedAt" not in body


def test_an_overdue_board_is_flagged_rather_than_hidden(db_session, monkeypatch):
    """An old board of honestly-dated fares is still useful; it just must not
    imply it was refreshed a moment ago."""
    monkeypatch.setattr(settings, "featured_deal_stale_after_hours", 6)
    old = plant_board(db_session, generated_at=datetime.utcnow() - timedelta(hours=9))
    recent = plant_board(db_session, generated_at=datetime.utcnow())

    assert board_is_stale(old) is True
    assert board_is_stale(recent) is False


# --- Refresh behaviour ------------------------------------------------------

def test_a_refresh_that_finds_nothing_keeps_the_previous_board(db_session, monkeypatch):
    """A provider outage must not blank the homepage.

    An older board is a better answer than an empty one, and the page already
    says how old every fare in it is.
    """
    plant_board(db_session, trips=[{"id": "existing"}])

    class EmptyRegistry:
        def run_tool(self, *args, **kwargs):
            return type("Result", (), {"trips": []})()

    monkeypatch.setattr("app.deals.featured.build_default_tool_registry", lambda: EmptyRegistry())

    result = refresh_featured_deals(db_session)

    assert result["refreshed"] is False
    surviving = latest_snapshot(db_session)
    assert surviving.trips == [{"id": "existing"}]


def test_a_failing_refresh_reports_rather_than_raising(db_session, monkeypatch):
    """The scheduled tick must continue to its other jobs."""

    class BrokenRegistry:
        def run_tool(self, *args, **kwargs):
            raise RuntimeError("provider exploded")

    monkeypatch.setattr("app.deals.featured.build_default_tool_registry", lambda: BrokenRegistry())

    result = refresh_featured_deals(db_session)

    assert result["refreshed"] is False
    assert "provider exploded" in result["reason"]


def test_the_newest_board_wins(db_session):
    plant_board(db_session, trips=[{"id": "older"}], generated_at=datetime.utcnow() - timedelta(hours=2))
    plant_board(db_session, trips=[{"id": "newer"}], generated_at=datetime.utcnow())

    assert latest_snapshot(db_session).trips == [{"id": "newer"}]


def test_origins_are_configurable_and_default_sensibly(monkeypatch):
    monkeypatch.setattr(settings, "featured_deal_origins", None)
    assert "VIE" in featured_origins()

    monkeypatch.setattr(settings, "featured_deal_origins", "cdg, bcn ")
    assert featured_origins() == ["CDG", "BCN"]


def test_the_board_endpoint_is_rate_limited(client, db_session):
    plant_board(db_session)
    limit = settings.rate_limit_cheap_per_window
    for _ in range(limit):
        client.get("/featured-deals")

    assert client.get("/featured-deals").status_code == 429


def test_the_board_is_cacheable_since_everyone_gets_the_same_one(client, db_session):
    plant_board(db_session)

    response = client.get("/featured-deals")

    assert "max-age" in response.headers.get("Cache-Control", "")
