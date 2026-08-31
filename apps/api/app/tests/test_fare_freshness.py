"""How Triplet handles the age of a cached price.

Travelpayouts serves fares travellers searched in the past week, so a price has
an age we do not control: refetching the same route seconds apart returns the
same fares with the same sighting dates. Refresh cadence changes *coverage*, not
a given fare's age. What we can do is prefer fresh prices, refuse ancient ones,
and say how old each one is.
"""

from datetime import date, datetime, timedelta

import pytest

from app.config import settings
from app.deals.refresher import origins_to_warm
from app.db.models import SavedSearchDB, UserDB, UserTravelProfileDB
from app.models import TripSearchRequest
from app.providers.travelpayouts.mapper import RoundTripFare
from app.services.flight_search_service import FlightSearchService, fare_is_too_old
from app.services.trip_builder import build_round_trip_options
from app.services.trip_scoring import fare_age_days


TODAY = date(2026, 8, 31)


def request(**overrides) -> TripSearchRequest:
    values = dict(
        originAirports=["VIE"],
        destinationAirports=["BCN"],
        startDate=date(2026, 10, 1),
        endDate=date(2026, 10, 31),
        minTripLengthDays=3,
        maxTripLengthDays=10,
        maxBudget=600,
        maxGroundTransferHours=4,
        tripStyle="one city",
    )
    values.update(overrides)
    return TripSearchRequest(**values)


def fare(price: float, seen_days_ago: int | None) -> RoundTripFare:
    return RoundTripFare(
        origin="VIE", destination="BCN", price=price, currency="EUR",
        departureDate="2026-10-06", returnDate="2026-10-10",
        observedAt=None if seen_days_ago is None else datetime(2026, 8, 31) - timedelta(days=seen_days_ago),
    )


def test_fare_age_is_measured_from_the_providers_sighting():
    trip = build_round_trip_options([fare(90, 4)], request(), enforce_budget=False)[0]

    assert fare_age_days(trip, TODAY) == 4


def test_a_trip_with_no_sighting_date_reports_unknown_age():
    trip = build_round_trip_options([fare(90, None)], request(), enforce_budget=False)[0]

    assert fare_age_days(trip, TODAY) is None


def test_a_fresh_price_outranks_a_cheaper_stale_one():
    # Priced mid-budget so neither is pinned at the top of the score range.
    fresh = build_round_trip_options([fare(430, 0)], request(), enforce_budget=False)[0]
    stale = build_round_trip_options([fare(400, 6)], request(), enforce_budget=False)[0]

    assert fresh.dealScore > stale.dealScore
    assert any("last seen" in c.label for c in stale.dealScoreBreakdown)


def test_unknown_age_ranks_below_a_dated_fresh_price():
    known = build_round_trip_options([fare(400, 0)], request(), enforce_budget=False)[0]
    unknown = build_round_trip_options([fare(400, None)], request(), enforce_budget=False)[0]

    assert known.dealScore > unknown.dealScore


@pytest.mark.parametrize(
    ("seen_days_ago", "too_old"),
    [(0, False), (7, False), (8, True), (30, True), (None, False)],
)
def test_ancient_prices_are_refused_but_undated_ones_are_kept(seen_days_ago, too_old):
    assert fare_is_too_old(fare(90, seen_days_ago), today=TODAY) is too_old


def test_the_age_cap_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "max_fare_age_days", 2)

    assert fare_is_too_old(fare(90, 3), today=TODAY) is True
    assert fare_is_too_old(fare(90, 1), today=TODAY) is False


def test_stale_fares_never_reach_the_results(monkeypatch):
    monkeypatch.setattr(settings, "max_fare_age_days", 3)
    service = FlightSearchService(provider_name="database", provider=object())

    kept = service._filter_round_trip_fares([fare(90, 10), fare(120, 1)], request())

    assert [f.price for f in kept] == [120]


def test_the_hourly_refresh_covers_airports_people_actually_chose(db_session):
    user = UserDB(id="u1", email="a@example.com", password_hash="x")
    db_session.add(user)
    db_session.add(UserTravelProfileDB(user_id="u1", origin_airports=["MUC", "KLU"]))
    db_session.add(
        SavedSearchDB(
            id="s1", email="a@example.com", origin_airports=["RJK"], is_active=True,
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 31),
            min_trip_length_days=3, max_trip_length_days=7, max_budget=400,
            max_ground_transfer_hours=4, trip_style="one city", frequency="weekly",
            manage_token_hash="m", unsubscribe_token_hash="u",
        )
    )
    db_session.commit()

    warmed = origins_to_warm(db_session)

    # The seeded candidates, plus the airports this traveller actually uses.
    assert {"VIE", "LJU"} <= set(warmed)
    assert {"MUC", "KLU", "RJK"} <= set(warmed)


def test_warming_is_bounded_so_the_hourly_api_cost_stays_predictable(db_session):
    assert len(origins_to_warm(db_session, limit=3)) == 3


# --- Chained trips: staleness compounds, and cheapest selects for stale ---

from datetime import datetime as _dt  # noqa: E402

from app.providers.travelpayouts.mapper import OneWayFare  # noqa: E402
from app.services.itinerary_builder import build_itineraries, plan_route  # noqa: E402
from app.services.trip_scoring import fare_age_days  # noqa: E402


def leg_fare(origin, destination, day, price, hours_old) -> OneWayFare:
    return OneWayFare(
        origin=origin, destination=destination, departureDate=f"2026-10-{day:02d}",
        price=price, currency="EUR", stops=0,
        observedAt=_dt(2026, 8, 31, 12) - timedelta(hours=hours_old),
    )


def chain_request(**overrides) -> TripSearchRequest:
    values = dict(
        originAirports=["VIE"], startDate=date(2026, 10, 1), endDate=date(2026, 10, 10),
        minTripLengthDays=4, maxTripLengthDays=14, maxBudget=1000, maxGroundTransferHours=6,
        tripStyle="surprise me", tripPlan="multi_city", routeStops=["BCN", "LIS"],
    )
    values.update(overrides)
    return TripSearchRequest(**values)


def test_a_leg_prefers_a_fresh_fare_over_a_cheaper_stale_one(monkeypatch):
    """The bargain on a route is usually the fare that has since risen.

    Vienna-Stockholm's cheapest was EUR 26 and 63 hours old while the cheapest
    seen that day was EUR 34. Summed across a chain, choosing the stale one every
    time is what pushed a quoted EUR 112 trip to EUR 148 on the booking page.
    """
    monkeypatch.setattr(settings, "itinerary_leg_fare_max_age_hours", 24)
    monkeypatch.setattr("app.services.itinerary_builder.datetime", _FrozenClock)
    ask = chain_request()
    legs = plan_route(ask, "VIE")
    fares = {
        ("VIE", "BCN"): [leg_fare("VIE", "BCN", d, 26, 63) for d in range(1, 20)]
        + [leg_fare("VIE", "BCN", d, 34, 3) for d in range(1, 20)],
        ("BCN", "LIS"): [leg_fare("BCN", "LIS", d, 30, 5) for d in range(1, 26)],
        ("LIS", "VIE"): [leg_fare("LIS", "VIE", d, 46, 6) for d in range(1, 26)],
    }

    trip = build_itineraries(ask, "VIE", legs, fares)[0]

    assert trip.totalPrice == 110  # 34 + 30 + 46, not 26 + 30 + 46
    assert all(
        segment.flight.observedAt >= _dt(2026, 8, 30, 12)
        for segment in trip.segments
        if segment.kind == "flight"
    )


def test_a_leg_with_nothing_fresh_still_uses_what_it_has(monkeypatch):
    """A thin route with an older price is still a real answer."""
    monkeypatch.setattr(settings, "itinerary_leg_fare_max_age_hours", 24)
    monkeypatch.setattr("app.services.itinerary_builder.datetime", _FrozenClock)
    ask = chain_request()
    legs = plan_route(ask, "VIE")
    fares = {
        ("VIE", "BCN"): [leg_fare("VIE", "BCN", d, 34, 3) for d in range(1, 26)],
        ("BCN", "LIS"): [leg_fare("BCN", "LIS", d, 30, 90) for d in range(1, 26)],  # all stale
        ("LIS", "VIE"): [leg_fare("LIS", "VIE", d, 46, 6) for d in range(1, 26)],
    }

    trips = build_itineraries(ask, "VIE", legs, fares)

    assert trips and trips[0].totalPrice == 110


def test_a_chained_trip_reports_the_age_of_its_stalest_leg(monkeypatch):
    monkeypatch.setattr(settings, "itinerary_leg_fare_max_age_hours", 400)
    monkeypatch.setattr("app.services.itinerary_builder.datetime", _FrozenClock)
    ask = chain_request()
    legs = plan_route(ask, "VIE")
    fares = {
        ("VIE", "BCN"): [leg_fare("VIE", "BCN", d, 34, 1) for d in range(1, 26)],
        ("BCN", "LIS"): [leg_fare("BCN", "LIS", d, 30, 96) for d in range(1, 26)],  # 4 days
        ("LIS", "VIE"): [leg_fare("LIS", "VIE", d, 46, 2) for d in range(1, 26)],
    }

    trip = build_itineraries(ask, "VIE", legs, fares)[0]

    # Not the freshest leg's one hour: the total is only as good as its worst part.
    assert fare_age_days(trip, today=date(2026, 8, 31)) == 4


def test_a_chained_trip_says_its_total_is_separate_tickets():
    from app.tools.travel_tools import _finish_itinerary
    from app.services.trip_scoring import ScoringContext

    ask = chain_request()
    legs = plan_route(ask, "VIE")
    fares = {
        ("VIE", "BCN"): [leg_fare("VIE", "BCN", d, 34, 1) for d in range(1, 26)],
        ("BCN", "LIS"): [leg_fare("BCN", "LIS", d, 30, 1) for d in range(1, 26)],
        ("LIS", "VIE"): [leg_fare("LIS", "VIE", d, 46, 1) for d in range(1, 26)],
    }
    trip = build_itineraries(ask, "VIE", legs, fares)[0]
    _finish_itinerary(trip, ask, ScoringContext())

    assert any("own one-way ticket" in warning for warning in trip.warnings)
    # Every hop is checkable on its own, since that is what was priced.
    assert all(
        segment.bookingUrl for segment in trip.segments if segment.kind == "flight"
    )


class _FrozenClock:
    """Pins "now" so fare ages in these tests are deterministic."""

    @staticmethod
    def utcnow():
        return _dt(2026, 8, 31, 12)

    @staticmethod
    def combine(*args, **kwargs):
        return _dt.combine(*args, **kwargs)
