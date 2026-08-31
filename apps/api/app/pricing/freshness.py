"""How old a fare is, and how much that should count for.

Travelpayouts serves recently observed fares, not live inventory, so every price
Triplet shows has an age. Age is the single most useful thing we know about a
cached price, and it is computed in exactly one place: scattering
`datetime.utcnow()` subtractions through builders and components is how the same
fare ends up described three different ways on one screen.

A caveat that shapes the whole model: only two of the four endpoints we use can
date a fare at all.

  * ``v2/prices/month-matrix`` returns ``found_at`` — a real timestamp.
  * ``v3/prices_for_dates`` hides the date inside its booking link as
    ``search_date=DDMMYYYY`` — day precision only.
  * ``v1/prices/calendar`` and ``v1/city-directions`` return no age whatsoever.

So "unknown" is a real, common state rather than an edge case, and it is scored
between aging and stale: not knowing is worse than a fare we know is a day old,
better than one we know is three days old.

``expires_at`` is deliberately NOT used. It looks like fare validity but is the
response cache window: all 55 rows of a route carry the identical value, roughly
one hour ahead, and it moves by a second between requests. Treating it as fare
validity would discard every result an hour after each fetch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Freshness = Literal["fresh", "recent", "aging", "stale", "unknown"]


@dataclass(frozen=True)
class FreshnessBand:
    max_age_hours: float
    label: Freshness
    score: int


# Ordered by age. The first band whose ceiling the fare falls under wins.
FRESHNESS_BANDS: tuple[FreshnessBand, ...] = (
    FreshnessBand(6, "fresh", 100),
    FreshnessBand(12, "fresh", 90),
    FreshnessBand(24, "recent", 75),
    FreshnessBand(36, "aging", 55),
    FreshnessBand(48, "aging", 35),
)
STALE_SCORE = 15
UNKNOWN_SCORE = 40
STALE_AFTER_HOURS = 48.0


@dataclass(frozen=True)
class FreshnessVerdict:
    label: Freshness
    score: int
    age_hours: float | None

    @property
    def is_stale(self) -> bool:
        return self.label == "stale"


def evaluate_freshness(observed_at: datetime | None, now: datetime | None = None) -> FreshnessVerdict:
    """Grade one fare by how long ago the provider saw it."""
    if observed_at is None:
        return FreshnessVerdict(label="unknown", score=UNKNOWN_SCORE, age_hours=None)
    reference = now or datetime.utcnow()
    age_hours = max(0.0, (reference - observed_at).total_seconds() / 3600)
    for band in FRESHNESS_BANDS:
        if age_hours < band.max_age_hours:
            return FreshnessVerdict(label=band.label, score=band.score, age_hours=age_hours)
    return FreshnessVerdict(label="stale", score=STALE_SCORE, age_hours=age_hours)


def combine_freshness(
    observed_ats: list[datetime | None],
    now: datetime | None = None,
) -> FreshnessVerdict:
    """Grade a multi-leg trip by its WEAKEST leg.

    A composite price is only as trustworthy as its worst component: averaging a
    two-hour-old leg with a thirty-hour-old one would advertise a confidence the
    itinerary does not have. An undated leg drags the whole trip to "unknown" for
    the same reason.
    """
    if not observed_ats:
        return FreshnessVerdict(label="unknown", score=UNKNOWN_SCORE, age_hours=None)
    verdicts = [evaluate_freshness(value, now) for value in observed_ats]
    return min(verdicts, key=lambda verdict: verdict.score)
