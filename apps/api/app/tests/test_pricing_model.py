"""The canonical price model: what a number is, and how sure we are of it.

Triplet shows recently observed fares, never live inventory. These tests pin the
distinctions that keep that honest — an observation of a whole trip is not the
same as a sum of observations, and a composite is only as fresh as its worst leg.
"""

from datetime import date, datetime, timedelta

import pytest

from app.models import TripSearchRequest
from app.pricing import build_price_info, combine_freshness, evaluate_freshness
from app.providers.travelpayouts.mapper import OneWayFare, RoundTripFare
from app.services.itinerary_builder import build_itineraries, plan_route
from app.services.trip_builder import build_round_trip_options

NOW = datetime(2026, 8, 31, 12)


@pytest.mark.parametrize(
    ("age_hours", "label", "score"),
    [(2, "fresh", 100), (10, "fresh", 90), (20, "recent", 75),
     (30, "aging", 55), (46, "aging", 35), (60, "stale", 15)],
)
def test_freshness_bands(age_hours, label, score):
    verdict = evaluate_freshness(NOW - timedelta(hours=age_hours), NOW)

    assert (verdict.label, verdict.score) == (label, score)


def test_an_undated_fare_is_unknown_not_fresh_and_not_stale():
    verdict = evaluate_freshness(None, NOW)

    assert verdict.label == "unknown"
    # Between "aging" and "stale": not knowing is worse than a day-old fare,
    # better than one we know is three days old.
    assert 15 < verdict.score < 55


def test_a_composite_takes_the_age_of_its_weakest_leg():
    verdict = combine_freshness(
        [NOW - timedelta(hours=2), NOW - timedelta(hours=6), NOW - timedelta(hours=31)],
        NOW,
    )

    assert verdict.label == "aging"
    assert verdict.age_hours == 31


def test_one_undated_leg_drags_the_whole_itinerary_to_unknown():
    verdict = combine_freshness([NOW - timedelta(hours=1), None], NOW)

    assert verdict.label == "unknown"


def test_a_price_built_from_several_legs_reports_the_oldest_sighting():
    info = build_price_info(
        amount=365, kind="estimated_multi_city",
        observed_ats=[NOW - timedelta(hours=4), NOW - timedelta(hours=7), NOW - timedelta(hours=29)],
        now=NOW,
    )

    assert info.isEstimate is True
    assert info.legCount == 3
    assert info.ageHours == 29
    assert info.freshness == "aging"


def request(**overrides) -> TripSearchRequest:
    values = dict(
        originAirports=["VIE"], destinationAirports=["BCN"],
        startDate=date(2026, 10, 1), endDate=date(2026, 10, 31),
        minTripLengthDays=3, maxTripLengthDays=14, maxBudget=1000,
        maxGroundTransferHours=6, tripStyle="one city",
    )
    values.update(overrides)
    return TripSearchRequest(**values)


def test_an_observed_return_fare_is_not_an_estimate():
    """The provider saw this whole trip priced. That is the strongest case."""
    fare = RoundTripFare(
        origin="VIE", destination="BCN", price=83, currency="EUR",
        departureDate="2026-10-18", returnDate="2026-10-22",
        observedAt=datetime.utcnow() - timedelta(hours=3),
    )

    trip = build_round_trip_options([fare], request(), enforce_budget=False)[0]

    assert trip.price.kind == "cached_return"
    assert trip.price.isEstimate is False
    assert trip.price.legCount == 1
    assert trip.price.amount == 83


def test_a_multi_city_total_is_marked_as_an_estimate():
    ask = request(destinationAirports=None, tripPlan="multi_city", routeStops=["BCN", "LIS"])
    legs = plan_route(ask, "VIE")
    recent = datetime.utcnow() - timedelta(hours=2)
    fares = {
        ("VIE", "BCN"): [OneWayFare(origin="VIE", destination="BCN", departureDate=f"2026-10-{d:02d}",
                                    price=50, observedAt=recent) for d in range(1, 26)],
        ("BCN", "LIS"): [OneWayFare(origin="BCN", destination="LIS", departureDate=f"2026-10-{d:02d}",
                                    price=30, observedAt=recent) for d in range(1, 26)],
        ("LIS", "VIE"): [OneWayFare(origin="LIS", destination="VIE", departureDate=f"2026-10-{d:02d}",
                                    price=70, observedAt=recent) for d in range(1, 26)],
    }

    trip = build_itineraries(ask, "VIE", legs, fares)[0]

    assert trip.price.kind == "estimated_multi_city"
    assert trip.price.isEstimate is True
    assert trip.price.legCount == 3
    assert trip.price.amount == 150


def test_an_open_jaw_total_is_marked_as_an_estimate():
    ask = request(
        destinationAirports=["STO"], returnOriginAirports=["HEL"], tripPlan="open_jaw",
    )
    legs = plan_route(ask, "BUD")
    recent = datetime.utcnow() - timedelta(hours=2)
    fares = {
        ("BUD", "STO"): [OneWayFare(origin="BUD", destination="STO", departureDate=f"2026-10-{d:02d}",
                                    price=80, observedAt=recent) for d in range(1, 26)],
        ("HEL", "BUD"): [OneWayFare(origin="HEL", destination="BUD", departureDate=f"2026-10-{d:02d}",
                                    price=90, observedAt=recent) for d in range(1, 26)],
    }

    trip = build_itineraries(ask, "BUD", legs, fares)[0]

    assert trip.price.kind == "estimated_open_jaw"
    assert trip.price.isEstimate is True
    # The overland crossing is never in the priced total.
    assert trip.price.amount == 170
    assert trip.groundEstimate and trip.groundEstimate > 0
