"""The homepage deal board: computed on a schedule, served from the database.

The landing page used to run a full trip search on every page view. That is a
real provider search with real cost, repeated for every visitor — and for every
crawler, preview bot and uptime check that ever loads the front page. It also
meant the homepage was slowest and most expensive exactly when it was most
popular.

The board is now assembled by the hourly tick and stored whole. Serving it is
one indexed read and no provider call at all.

Two clocks are kept apart on purpose, because conflating them would be a lie the
whole application is otherwise careful not to tell:

  * ``generatedAt`` — when Triplet last assembled this board.
  * each trip's own ``price.observedAt`` — when that fare was actually seen.

Refreshing the board hourly does not make the fares in it an hour old. They are
whatever age the provider's data is, and each one still says so.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.db.models import FeaturedDealSnapshotDB
from app.models import TripSearchRequest
from app.tools.base import ToolContext
from app.tools.registry import build_default_tool_registry

logger = logging.getLogger(__name__)

#: Origins the public board is built from. Anonymous visitors have not told us
#: where they fly from, so this is labelled as an example in the interface
#: rather than presented as "your airports" — see the landing page copy.
DEFAULT_FEATURED_ORIGINS = ("VIE", "ZAG", "TRS", "VCE", "BUD", "LJU")

#: How many deals the board holds.
FEATURED_DEAL_COUNT = 6

#: Snapshots kept for history. Enough to see what changed, not a growing table.
SNAPSHOTS_RETAINED = 5


def featured_origins() -> list[str]:
    configured = settings.featured_deal_origins
    if configured:
        return [code.strip().upper() for code in configured.split(",") if code.strip()]
    return list(DEFAULT_FEATURED_ORIGINS)


def _board_request() -> TripSearchRequest:
    """The curated search behind the board.

    Deliberately broad and cheap: no destination, a wide date window, a short
    trip length and a low budget ceiling — the shape that surfaces the genuinely
    striking fares a landing page exists to show.
    """
    today = date.today()
    return TripSearchRequest(
        originAirports=featured_origins(),
        destinationAirports=None,
        startDate=today + timedelta(days=7),
        endDate=today + timedelta(days=75),
        minTripLengthDays=3,
        maxTripLengthDays=8,
        maxBudget=settings.featured_deal_max_budget,
        maxGroundTransferHours=4,
        tripStyle="surprise me",
        directOnly=False,
    )


def refresh_featured_deals(db=None) -> dict:
    """Rebuild the board. Called by the scheduled tick, never by a request."""
    owns_session = db is None
    session = db or SessionLocal()
    try:
        registry = build_default_tool_registry()
        result = registry.run_tool("search_trips", _board_request(), ToolContext(db=session))
        trips = result.trips[:FEATURED_DEAL_COUNT]

        if not trips:
            # Keep the existing board rather than replacing it with an empty
            # one. A provider outage should not blank the homepage; a slightly
            # older board is a better answer than no board.
            logger.warning("featured_deals_refresh_empty keeping_previous=true")
            return {"refreshed": False, "reason": "no trips returned", "count": 0}

        snapshot = FeaturedDealSnapshotDB(
            generated_at=datetime.utcnow(),
            trips=[trip.model_dump(mode="json") for trip in trips],
            origin_airports=featured_origins(),
            trip_count=len(trips),
        )
        session.add(snapshot)
        session.commit()
        _prune_old_snapshots(session)
        logger.info("featured_deals_refreshed count=%s", len(trips))
        return {"refreshed": True, "count": len(trips)}
    except Exception as exc:  # noqa: BLE001 - the tick logs and continues
        session.rollback()
        logger.exception("featured_deals_refresh_failed")
        return {"refreshed": False, "reason": str(exc), "count": 0}
    finally:
        if owns_session:
            session.close()


def _prune_old_snapshots(db) -> None:
    keep = list(
        db.scalars(
            select(FeaturedDealSnapshotDB.id)
            .order_by(FeaturedDealSnapshotDB.generated_at.desc())
            .limit(SNAPSHOTS_RETAINED)
        ).all()
    )
    if not keep:
        return
    stale = db.scalars(
        select(FeaturedDealSnapshotDB).where(FeaturedDealSnapshotDB.id.notin_(keep))
    ).all()
    for row in stale:
        db.delete(row)
    if stale:
        db.commit()


def latest_snapshot(db) -> FeaturedDealSnapshotDB | None:
    return db.scalar(
        select(FeaturedDealSnapshotDB).order_by(FeaturedDealSnapshotDB.generated_at.desc()).limit(1)
    )


def board_is_stale(snapshot: FeaturedDealSnapshotDB, now: datetime | None = None) -> bool:
    """Whether the board is old enough that the page should say so.

    Not a reason to hide it — an old board of honestly-dated fares is still
    useful — but the page should not imply it was just refreshed.
    """
    now = now or datetime.utcnow()
    age = now - snapshot.generated_at
    return age > timedelta(hours=settings.featured_deal_stale_after_hours)
