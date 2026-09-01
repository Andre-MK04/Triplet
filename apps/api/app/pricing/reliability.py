"""How well Triplet's observed fares hold up when someone checks them.

Triplet shows prices it has seen rather than live inventory, and has always said
so. What it could not say was *how far* they drift — "recently observed" is
honest but vague, and the difference between a two-hour-old fare and a two-day-
old one has been an assumption rather than a measurement.

This turns that into something measured. When a traveller follows a live-price
link and later tells Triplet whether the price still held, the answer is stored
against the fare's properties: route, age band, fare kind, provider.

Two rules govern what may be said with it.

Nothing is attributed to a person. The question is about fares, not travellers,
so nothing here records who answered.

Nothing is published from a handful of answers. A route with three reports says
nothing about that route, and a reliability label drawn from it would be worse
than silence — travellers would weigh it as evidence. Aggregates return their
sample size and a flag for whether it is enough; callers must honour it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import func, select

from app.db.models import FareFeedbackDB

#: What a traveller can report. Never an exact external price: asking someone to
#: transcribe a number from another site produces guesses, and a band is what
#: the question actually needs.
FeedbackResponse = Literal["matched", "slightly_higher", "much_higher", "unavailable"]

VALID_RESPONSES: frozenset[str] = frozenset(
    {"matched", "slightly_higher", "much_higher", "unavailable"}
)

#: Answers that mean the traveller could still have booked at roughly the price
#: Triplet showed. "slightly_higher" counts: fares move, and a small move is the
#: normal condition of the market rather than a failure of the observation.
CLOSE_ENOUGH: frozenset[str] = frozenset({"matched", "slightly_higher"})

#: Below this, a group is not reported on at all. Chosen to be clearly too small
#: to read anything into rather than to be a precise statistical threshold.
MIN_SAMPLE_FOR_REPORTING = 20

VALID_AGE_BUCKETS: frozenset[str] = frozenset({"fresh", "recent", "aging", "stale", "unknown"})


@dataclass(frozen=True)
class ReliabilitySummary:
    """How often fares in one group still held up. Sample size always included."""

    group: str
    sampleCount: int
    closeRate: float | None
    unavailableRate: float | None
    #: False when the group is too small to say anything about. Callers must not
    #: show a rate when this is False — the rate is present for internal use.
    isReportable: bool

    @property
    def close_percentage(self) -> int | None:
        return None if self.closeRate is None else round(self.closeRate * 100)


def record_feedback(
    db,
    *,
    check_id: str,
    origin: str,
    destination: str,
    trip_type: str,
    fare_kind: str,
    fare_age_bucket: str,
    shown_price: float,
    response: str,
    currency: str = "EUR",
    provider: str | None = None,
) -> bool:
    """Store one answer. False when this check has already been answered.

    Idempotent on check_id, so a double submit or a retried request records one
    answer rather than two — otherwise a stubborn browser could quietly weight
    the aggregates.
    """
    if response not in VALID_RESPONSES:
        raise ValueError(f"Unknown feedback response: {response!r}")
    if fare_age_bucket not in VALID_AGE_BUCKETS:
        raise ValueError(f"Unknown fare age bucket: {fare_age_bucket!r}")

    already = db.scalar(select(FareFeedbackDB.id).where(FareFeedbackDB.check_id == check_id))
    if already is not None:
        return False

    db.add(
        FareFeedbackDB(
            check_id=check_id,
            origin=origin.strip().upper()[:8],
            destination=destination.strip().upper()[:8],
            trip_type=trip_type,
            fare_kind=fare_kind,
            provider=provider,
            fare_age_bucket=fare_age_bucket,
            shown_price=float(shown_price),
            currency=currency,
            response=response,
        )
    )
    db.commit()
    return True


def _summarise(rows: list[tuple[str, int]], group: str) -> ReliabilitySummary:
    total = sum(count for _, count in rows)
    if total == 0:
        return ReliabilitySummary(group=group, sampleCount=0, closeRate=None,
                                  unavailableRate=None, isReportable=False)
    close = sum(count for response, count in rows if response in CLOSE_ENOUGH)
    gone = sum(count for response, count in rows if response == "unavailable")
    return ReliabilitySummary(
        group=group,
        sampleCount=total,
        closeRate=close / total,
        unavailableRate=gone / total,
        isReportable=total >= MIN_SAMPLE_FOR_REPORTING,
    )


def _counts_by(db, grouping_column, since: datetime | None):
    query = select(grouping_column, FareFeedbackDB.response, func.count()).group_by(
        grouping_column, FareFeedbackDB.response
    )
    if since is not None:
        query = query.where(FareFeedbackDB.created_at >= since)
    return db.execute(query).all()


def reliability_by_age_bucket(db, since_days: int | None = 90) -> list[ReliabilitySummary]:
    """The question this whole table exists to answer.

    If fares hold up markedly worse past a certain age, that is an argument for
    ranking them lower or refusing to show them — grounded in measurement rather
    than in the guess the freshness weights currently encode.
    """
    since = datetime.utcnow() - timedelta(days=since_days) if since_days else None
    grouped: dict[str, list[tuple[str, int]]] = {}
    for bucket, response, count in _counts_by(db, FareFeedbackDB.fare_age_bucket, since):
        grouped.setdefault(bucket, []).append((response, count))
    return sorted(
        (_summarise(rows, bucket) for bucket, rows in grouped.items()),
        key=lambda summary: summary.group,
    )


def reliability_by_fare_kind(db, since_days: int | None = 90) -> list[ReliabilitySummary]:
    """Whether assembled estimates hold up as well as observed single fares.

    Triplet already labels them differently; this is how it would learn whether
    the distinction is as large in practice as it is in principle.
    """
    since = datetime.utcnow() - timedelta(days=since_days) if since_days else None
    grouped: dict[str, list[tuple[str, int]]] = {}
    for kind, response, count in _counts_by(db, FareFeedbackDB.fare_kind, since):
        grouped.setdefault(kind, []).append((response, count))
    return sorted(
        (_summarise(rows, kind) for kind, rows in grouped.items()),
        key=lambda summary: summary.group,
    )


def reliability_by_provider(db, since_days: int | None = 90) -> list[ReliabilitySummary]:
    since = datetime.utcnow() - timedelta(days=since_days) if since_days else None
    grouped: dict[str, list[tuple[str, int]]] = {}
    for provider, response, count in _counts_by(db, FareFeedbackDB.provider, since):
        grouped.setdefault(provider or "unknown", []).append((response, count))
    return sorted(
        (_summarise(rows, provider) for provider, rows in grouped.items()),
        key=lambda summary: summary.group,
    )


def reliability_for_route(
    db, origin: str, destination: str, since_days: int | None = 90
) -> ReliabilitySummary:
    """One route's record.

    Almost always below the reporting threshold, which is the point: a
    per-route reliability label is the most tempting thing to build here and the
    least defensible, because the sample is thinnest exactly where the claim
    would be most specific.
    """
    since = datetime.utcnow() - timedelta(days=since_days) if since_days else None
    query = (
        select(FareFeedbackDB.response, func.count())
        .where(
            FareFeedbackDB.origin == origin.strip().upper(),
            FareFeedbackDB.destination == destination.strip().upper(),
        )
        .group_by(FareFeedbackDB.response)
    )
    if since is not None:
        query = query.where(FareFeedbackDB.created_at >= since)
    rows = [(response, count) for response, count in db.execute(query).all()]
    return _summarise(rows, f"{origin.upper()}-{destination.upper()}")


def overall_reliability(db, since_days: int | None = 90) -> ReliabilitySummary:
    since = datetime.utcnow() - timedelta(days=since_days) if since_days else None
    query = select(FareFeedbackDB.response, func.count()).group_by(FareFeedbackDB.response)
    if since is not None:
        query = query.where(FareFeedbackDB.created_at >= since)
    rows = [(response, count) for response, count in db.execute(query).all()]
    return _summarise(rows, "all")
