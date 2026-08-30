"""Thin routes: when the provider's cache holds nothing of the requested shape.

Travelpayouts only holds fares travellers have recently searched, so a real route
can genuinely have no fare of the requested length — Vienna→Dublin has September
fares, but only 2-4 night ones. A bare "no trips" reads as a Triplet failure, so
the search falls back to the closest real fares and says what it loosened.
"""

from datetime import date

from app.models import TripSearchRequest
from app.providers.travelpayouts.mapper import RoundTripFare
from app.services.destination_scope import resolve_destination_scope
from app.services.trip_scoring import ScoringContext
from app.tools.travel_tools import nearest_matches


def request(**overrides) -> TripSearchRequest:
    values = dict(
        originAirports=["VIE"],
        destinationAirports=["DUB"],
        startDate=date(2026, 9, 1),
        endDate=date(2026, 9, 30),
        minTripLengthDays=6,
        maxTripLengthDays=8,
        maxBudget=600,
        maxGroundTransferHours=4,
        tripStyle="one city",
    )
    values.update(overrides)
    return TripSearchRequest(**values)


def dublin_fares() -> list[RoundTripFare]:
    """Real shape of what the provider holds: September, but only short breaks."""
    return [
        RoundTripFare(origin="VIE", destination="DUB", price=123, currency="EUR",
                      departureDate="2026-09-17", returnDate="2026-09-19"),
        RoundTripFare(origin="VIE", destination="DUB", price=144, currency="EUR",
                      departureDate="2026-09-25", returnDate="2026-09-29"),
        # A week-long fare exists, but in October.
        RoundTripFare(origin="VIE", destination="DUB", price=86, currency="EUR",
                      departureDate="2026-10-13", returnDate="2026-10-20"),
    ]


def nearest(req: TripSearchRequest, fares: list[RoundTripFare]):
    return nearest_matches(
        fares,
        req,
        resolve_destination_scope(req),
        ScoringContext(),
        airports=[],
        transfers=[],
        flights=[],
    )


def test_offers_other_trip_lengths_before_it_offers_other_dates():
    trips, note = nearest(request(), dublin_fares())

    assert trips
    # The requested September window is preserved; only the length gave way.
    assert all(t.outboundFlight.departureDateTime.month == 9 for t in trips)
    assert "6–8 night" in note and "Dublin" in note
    assert "other trip lengths" in note


def test_offers_other_dates_when_no_length_fits_the_window():
    october_only = [dublin_fares()[2]]

    trips, note = nearest(request(), october_only)

    assert [t.outboundFlight.departureDateTime.date().isoformat() for t in trips] == ["2026-10-13"]
    assert "other dates" in note


def test_says_nothing_when_there_is_genuinely_nothing_to_offer():
    trips, note = nearest(request(), [])

    assert trips == []
    assert note is None


def test_nearest_matches_never_reshapes_a_fare_to_look_like_a_match():
    trips, _ = nearest(request(), dublin_fares())

    # Every option keeps the real dates and price of the fare it came from.
    offered = {
        (t.outboundFlight.departureDateTime.date().isoformat(), t.totalPrice) for t in trips
    }
    assert offered <= {("2026-09-17", 123.0), ("2026-09-25", 144.0)}
    assert all(t.nights not in range(6, 9) for t in trips)
