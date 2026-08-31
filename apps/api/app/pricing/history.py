"""Is this a good price? Answered only from what Triplet has actually seen.

Every claim here is grounded in observations Triplet collected from its own
flight-data source. The service never asserts a fare is purchasable, never
predicts, and stays silent when the evidence is thin — a badge on four
observations is worse than no badge, because it teaches travellers to distrust
the ones that mean something.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

Classification = Literal["exceptional", "great", "good", "typical", "high", "very_high"]
Confidence = Literal["insufficient", "low", "medium", "high"]

# How many comparable observations before we will say anything at all, and
# before we will say it firmly. A "great price" drawn from three sightings is a
# coin flip wearing a badge.
MIN_SAMPLE_FOR_ANY_CLAIM = 5
CONFIDENCE_THRESHOLDS: tuple[tuple[int, Confidence], ...] = (
    (40, "high"),
    (15, "medium"),
    (MIN_SAMPLE_FOR_ANY_CLAIM, "low"),
)

# Percentile ceilings, cheapest first.
CLASSIFICATION_BANDS: tuple[tuple[float, Classification], ...] = (
    (10, "exceptional"),
    (25, "great"),
    (45, "good"),
    (70, "typical"),
    (90, "high"),
    (100, "very_high"),
)

# Trips of wildly different lengths are not comparable prices.
NIGHT_BUCKETS: tuple[tuple[int, int], ...] = ((1, 3), (4, 6), (7, 10), (11, 16), (17, 30), (31, 365))
# How far either side of the departure date still counts as the same travel period.
NEAR_DATE_WINDOW_DAYS = 14


class PriceHistory(BaseModel):
    """What Triplet's own records say about a price. Attached to a trip's price."""

    available: bool = False
    sampleCount: int = 0
    classification: Classification | None = None
    confidence: Confidence = "insufficient"
    medianPrice: float | None = None
    typicalLow: float | None = None
    typicalHigh: float | None = None
    percentile: int | None = None
    #: Which comparison level produced this, for debugging and explanation.
    basis: str | None = None


@dataclass(frozen=True)
class ComparisonLevel:
    """One rung of the fallback ladder, most specific first."""

    name: str
    near_dates: bool
    same_nights_bucket: bool
    match_stops: bool


# Tried in order; the first rung with enough evidence wins. Each step down trades
# specificity for sample size, which is the honest trade when data is sparse.
COMPARISON_LEVELS: tuple[ComparisonLevel, ...] = (
    ComparisonLevel("similar dates and trip length", near_dates=True, same_nights_bucket=True, match_stops=True),
    ComparisonLevel("same month and trip length", near_dates=True, same_nights_bucket=True, match_stops=False),
    ComparisonLevel("same trip length on this route", near_dates=False, same_nights_bucket=True, match_stops=False),
    ComparisonLevel("this route overall", near_dates=False, same_nights_bucket=False, match_stops=False),
)


def nights_bucket(nights: int | None) -> tuple[int, int] | None:
    if nights is None:
        return None
    for low, high in NIGHT_BUCKETS:
        if low <= nights <= high:
            return (low, high)
    return None


def remove_outliers(prices: list[float]) -> list[float]:
    """Drop corrupted extremes without discarding genuine bargains.

    Airfare feeds carry EUR 1 glitches and first-class rows. Interquartile
    filtering handles those, but the fence is deliberately wide on the low side:
    an unusually cheap fare is the exact thing Triplet exists to find, and
    trimming it would make every real deal look ordinary. Raw rows are never
    modified — filtering happens here, in analysis.
    """
    if len(prices) < 8:
        return prices
    ordered = sorted(prices)
    q1 = _percentile_value(ordered, 25)
    q3 = _percentile_value(ordered, 75)
    spread = q3 - q1
    if spread <= 0:
        return prices
    low = q1 - 3.0 * spread
    high = q3 + 1.5 * spread
    return [price for price in ordered if low <= price <= high]


def _percentile_value(ordered: list[float], percentile: float) -> float:
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * (percentile / 100)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def percentile_of(price: float, prices: list[float]) -> int:
    """Share of observations at or below this price, 0-100."""
    if not prices:
        return 50
    below = sum(1 for value in prices if value < price)
    ties = sum(1 for value in prices if value == price)
    return int(round(100 * (below + ties / 2) / len(prices)))


def classify(percentile: int) -> Classification:
    for ceiling, label in CLASSIFICATION_BANDS:
        if percentile <= ceiling:
            return label
    return "very_high"


def confidence_for(sample_count: int) -> Confidence:
    for threshold, label in CONFIDENCE_THRESHOLDS:
        if sample_count >= threshold:
            return label
    return "insufficient"


def summarise(price: float, comparable: list[float], basis: str) -> PriceHistory:
    """Turn a set of comparable observations into a verdict."""
    cleaned = remove_outliers(comparable)
    if len(cleaned) < MIN_SAMPLE_FOR_ANY_CLAIM:
        return PriceHistory(available=False, sampleCount=len(cleaned))
    ordered = sorted(cleaned)
    percentile = percentile_of(price, ordered)
    return PriceHistory(
        available=True,
        sampleCount=len(ordered),
        classification=classify(percentile),
        confidence=confidence_for(len(ordered)),
        medianPrice=round(statistics.median(ordered), 2),
        typicalLow=round(_percentile_value(ordered, 25), 2),
        typicalHigh=round(_percentile_value(ordered, 75), 2),
        percentile=percentile,
        basis=basis,
    )


def date_window(departure: date) -> tuple[date, date]:
    return departure - timedelta(days=NEAR_DATE_WINDOW_DAYS), departure + timedelta(days=NEAR_DATE_WINDOW_DAYS)


# --------------------------------------------------------------------------
# Attaching history to a page of results
# --------------------------------------------------------------------------

# Composite totals are excluded from classification. A multi-city sum has no
# comparable population — Triplet has never observed that itinerary priced as a
# whole — so any badge on it would be a claim the data cannot support.
CLASSIFIABLE_KINDS = {"cached_return", "cached_one_way"}


def attach_price_history(db, trips: list) -> int:
    """Fill in each trip's price history, in one query for the whole page.

    Failure is silent by design: history is an enhancement, and a search that
    works is worth more than a badge. Returns how many trips were classified.
    """
    from app.db.repositories.price_observations_repository import PriceObservationsRepository

    candidates = [
        trip for trip in trips
        if trip.price and trip.price.kind in CLASSIFIABLE_KINDS and trip.totalPrice > 0
    ]
    if not candidates:
        return 0

    routes = {
        (
            trip.outboundFlight.origin,
            trip.outboundFlight.destination,
            "return" if trip.price.kind == "cached_return" else "one_way",
        )
        for trip in candidates
    }
    observations = PriceObservationsRepository(db).route_observations(list(routes))
    if not observations:
        return 0

    classified = 0
    for trip in candidates:
        trip_type = "return" if trip.price.kind == "cached_return" else "one_way"
        rows = observations.get(
            (trip.outboundFlight.origin.upper(), trip.outboundFlight.destination.upper(), trip_type)
        )
        if not rows:
            continue
        history = _analyse_trip(trip, rows)
        if history.available:
            trip.price.history = history
            classified += 1
    return classified


def _analyse_trip(trip, rows: list[tuple[float, date, int | None, int | None]]) -> PriceHistory:
    """Walk the comparison ladder until a rung has enough evidence."""
    departure = trip.outboundFlight.departureDateTime.date()
    window_start, window_end = date_window(departure)
    bucket = nights_bucket(trip.nights)
    is_direct = (trip.outboundFlight.stops or 0) == 0

    for level in COMPARISON_LEVELS:
        prices = [
            price
            for price, row_departure, row_nights, row_stops in rows
            if (not level.near_dates or window_start <= row_departure <= window_end)
            and (
                not level.same_nights_bucket
                or bucket is None
                or (row_nights is not None and bucket[0] <= row_nights <= bucket[1])
            )
            and (not level.match_stops or row_stops is None or ((row_stops == 0) == is_direct))
        ]
        summary = summarise(trip.totalPrice, prices, level.name)
        if summary.available:
            return summary
    return PriceHistory(available=False, sampleCount=0)
