"""The one place Triplet decides what a price *is*.

Every trip carries a PriceInfo saying where the number came from, whether it is
an observation or a sum of observations, and how old the oldest part of it is.
Builders fill this in; ranking and the interface read it. Nothing else recomputes
age or re-derives whether a price is an estimate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.pricing.freshness import Freshness, combine_freshness
from app.pricing.history import PriceHistory

PriceKind = Literal[
    # One provider observation of a complete round trip. The most trustworthy
    # thing we can show, because it is what Aviasales itself saw for this trip.
    "cached_return",
    # One provider observation of a single flight.
    "cached_one_way",
    # Separate observations added together. The sum is real arithmetic over real
    # fares, but no one ever saw this itinerary priced as a whole.
    "estimated_open_jaw",
    "estimated_multi_city",
    # Reserved: no live-fare source is configured today.
    "live",
]

ESTIMATED_KINDS = {"estimated_open_jaw", "estimated_multi_city"}


class PriceInfo(BaseModel):
    """What Triplet knows about a price, and how sure it is."""

    amount: float
    currency: str = "EUR"
    kind: PriceKind
    source: str = "travelpayouts-cache"
    isLive: bool = False
    #: True when the total is a sum of separately observed fares.
    isEstimate: bool = False
    #: When the provider last saw the price — the OLDEST leg for a composite.
    observedAt: datetime | None = None
    ageHours: float | None = None
    freshness: Freshness = "unknown"
    freshnessScore: int = 40
    #: How many separately priced flights make up the total.
    legCount: int = 1
    #: What Triplet's own observation history says about this price, when it has
    #: enough comparable records to say anything at all.
    history: PriceHistory | None = None


def build_price_info(
    amount: float,
    kind: PriceKind,
    observed_ats: list[datetime | None],
    currency: str = "EUR",
    source: str = "travelpayouts-cache",
    now: datetime | None = None,
) -> PriceInfo:
    verdict = combine_freshness(observed_ats, now)
    return PriceInfo(
        amount=round(amount, 2),
        currency=currency,
        kind=kind,
        source=source,
        isLive=kind == "live",
        isEstimate=kind in ESTIMATED_KINDS,
        observedAt=min((value for value in observed_ats if value), default=None),
        ageHours=round(verdict.age_hours, 1) if verdict.age_hours is not None else None,
        freshness=verdict.label,
        freshnessScore=verdict.score,
        legCount=max(1, len(observed_ats)),
    )
