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
