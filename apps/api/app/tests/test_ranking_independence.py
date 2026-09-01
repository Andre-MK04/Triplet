"""Ranking must not be for sale.

Triplet earns commission when a traveller books through an affiliate link, and
tells them so. That disclosure is only honest while the ranking is genuinely
blind to it — so this is asserted rather than promised.
"""

import inspect
from datetime import date

from app.models import TripSearchRequest
from app.services import trip_scoring
from app.services.trip_builder import build_round_trip_options
from app.providers.travelpayouts.mapper import RoundTripFare


def request() -> TripSearchRequest:
    return TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["BCN"],
        startDate=date(2026, 10, 1), endDate=date(2026, 10, 31),
        minTripLengthDays=3, maxTripLengthDays=10, maxBudget=600,
        maxGroundTransferHours=4, tripStyle="one city",
    )


def fare(price: float, booking_url: str | None) -> RoundTripFare:
    return RoundTripFare(
        origin="VIE", destination="BCN", price=price, currency="EUR",
        departureDate="2026-10-06", returnDate="2026-10-10",
        bookingUrl=booking_url,
    )


def test_the_scoring_module_never_reads_commercial_fields():
    """A structural check: the code cannot weigh what it never looks at."""
    source = inspect.getsource(trip_scoring)

    for term in ("affiliate", "marker", "commission", "bookingUrl", "providerDeepLink"):
        assert term not in source, f"ranking code now references {term!r}"


def test_an_affiliate_link_does_not_change_a_trip_score():
    """Same trip, same price — one monetisable, one not."""
    monetised = build_round_trip_options(
        [fare(400, "https://aviasales.com/x?marker=547063")], request(), enforce_budget=False
    )[0]
    plain = build_round_trip_options([fare(400, None)], request(), enforce_budget=False)[0]

    assert monetised.dealScore == plain.dealScore


def test_a_cheaper_trip_still_wins_when_only_the_pricier_one_pays():
    """The case where selling out would be profitable."""
    cheap_unmonetised = build_round_trip_options(
        [fare(200, None)], request(), enforce_budget=False
    )[0]
    dear_monetised = build_round_trip_options(
        [fare(500, "https://aviasales.com/x?marker=547063")], request(), enforce_budget=False
    )[0]

    assert cheap_unmonetised.dealScore > dear_monetised.dealScore
