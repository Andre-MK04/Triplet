"""Triplet's own fare-observation history: collection, and what it may claim.

The value of this table is that every number in it is something our data source
actually reported. These tests defend that: repeated retrieval of one cached
fare is one observation, composite totals Triplet computed never enter, and no
verdict is offered until the evidence supports one.
"""

from datetime import date, datetime, timedelta

import pytest

from app.db.models import PriceObservationDB
from app.db.repositories.price_observations_repository import PriceObservationsRepository
from app.pricing.history import (
    MIN_SAMPLE_FOR_ANY_CLAIM,
    classify,
    confidence_for,
    nights_bucket,
    percentile_of,
    remove_outliers,
    summarise,
)
from app.pricing.observation import FareObservation

FOUND = datetime(2026, 8, 31, 11, 32)


def observation(**overrides) -> FareObservation:
    values = dict(
        origin="VIE", destination="JFK", departure_date=date(2026, 9, 20),
        return_date=date(2026, 9, 27), price=347.0, currency="EUR",
        provider="travelpayouts", trip_type="return", found_at=FOUND,
    )
    values.update(overrides)
    return FareObservation(**values)


# ------------------------------------------------------------- deduplication

def test_the_same_cached_fare_retrieved_repeatedly_is_one_observation(db_session):
    """Five hundred people opening one cached fare is one piece of evidence."""
    repo = PriceObservationsRepository(db_session)
    retrievals = [
        observation(observed_at=FOUND + timedelta(hours=hours)) for hours in range(10)
    ]

    written = repo.record_observations(retrievals)

    assert written == 1
    assert db_session.query(PriceObservationDB).count() == 1


def test_a_new_price_event_is_a_new_observation(db_session):
    repo = PriceObservationsRepository(db_session)

    repo.record_observations([observation(price=347, found_at=datetime(2026, 8, 31, 10))])
    repo.record_observations([observation(price=361, found_at=datetime(2026, 8, 31, 14))])

    assert db_session.query(PriceObservationDB).count() == 2


def test_without_a_provider_timestamp_an_hour_bucket_holds_the_line(db_session):
    """Conservative: merging two events in an hour beats inflating the sample."""
    repo = PriceObservationsRepository(db_session)
    same_hour = [
        observation(found_at=None, observed_at=datetime(2026, 8, 31, 9, minute)) for minute in (1, 20, 55)
    ]

    assert repo.record_observations(same_hour) == 1
    assert repo.record_observations([observation(found_at=None, observed_at=datetime(2026, 8, 31, 10, 5))]) == 1


def test_deduplication_survives_a_batch_containing_its_own_repeats(db_session):
    repo = PriceObservationsRepository(db_session)

    assert repo.record_observations([observation(), observation(), observation()]) == 1


# ----------------------------------------------------------------- integrity

def test_a_composite_estimate_never_enters_the_history(db_session):
    """A total Triplet computed is not something the provider observed."""
    repo = PriceObservationsRepository(db_session)

    written = repo.record_observations([observation(price=365, kind="composite_estimate")])

    assert written == 0
    assert db_session.query(PriceObservationDB).count() == 0


@pytest.mark.parametrize(
    "broken",
    [
        {"price": 0},
        {"price": -20},
        {"price": 90_000},
        {"currency": "EU"},
        {"destination": "VIE"},
        {"return_date": date(2026, 9, 1)},
    ],
)
def test_corrupted_rows_are_refused(db_session, broken):
    repo = PriceObservationsRepository(db_session)

    assert repo.record_observations([observation(**broken)]) == 0


def test_a_return_observation_keeps_both_dates_and_its_length(db_session):
    repo = PriceObservationsRepository(db_session)
    repo.record_observations([observation()])

    row = db_session.query(PriceObservationDB).one()
    assert row.trip_type == "return"
    assert row.return_date == date(2026, 9, 27)
    assert row.nights == 7
    # Provider sighting and our retrieval are kept apart.
    assert row.found_at == FOUND
    assert row.observed_at is not None


def test_history_records_nothing_about_the_person_searching(db_session):
    repo = PriceObservationsRepository(db_session)
    repo.record_observations([observation()])

    row = db_session.query(PriceObservationDB).one()
    columns = {column.name for column in row.__table__.columns}
    assert not columns & {"user_id", "email", "ip", "ip_hash", "session_id"}


# ---------------------------------------------------------------- statistics

def test_outliers_are_dropped_without_discarding_genuine_bargains():
    prices = [1.0, 380, 390, 400, 410, 420, 430, 440, 5000.0]

    cleaned = remove_outliers(prices)

    assert 1.0 not in cleaned and 5000.0 not in cleaned
    assert 380 in cleaned and 440 in cleaned


def test_statistics_are_robust_rather_than_a_bare_average():
    prices = [389, 421, 405, 367, 438, 410, 351, 395, 462, 415, 382, 447, 359, 401, 430]

    summary = summarise(347, prices, "similar dates and trip length")

    assert summary.available
    assert summary.medianPrice == 405
    assert summary.typicalLow and summary.typicalHigh
    assert summary.typicalLow < summary.medianPrice < summary.typicalHigh
    assert summary.percentile == 0
    assert summary.classification == "exceptional"


@pytest.mark.parametrize(
    ("percentile", "expected"),
    [(5, "exceptional"), (20, "great"), (35, "good"), (50, "typical"), (80, "high"), (95, "very_high")],
)
def test_classification_bands(percentile, expected):
    assert classify(percentile) == expected


@pytest.mark.parametrize(
    ("samples", "expected"),
    [(3, "insufficient"), (8, "low"), (20, "medium"), (60, "high")],
)
def test_confidence_follows_sample_size(samples, expected):
    assert confidence_for(samples) == expected


def test_no_verdict_at_all_from_a_handful_of_observations():
    summary = summarise(347, [400, 410, 420], "this route overall")

    assert summary.available is False
    assert summary.classification is None


def test_percentile_places_a_price_within_what_we_have_seen():
    prices = [100, 200, 300, 400, 500]

    assert percentile_of(90, prices) == 0
    assert percentile_of(300, prices) == 50
    assert percentile_of(600, prices) == 100


@pytest.mark.parametrize(
    ("nights", "bucket"),
    [(2, (1, 3)), (5, (4, 6)), (7, (7, 10)), (14, (11, 16)), (25, (17, 30)), (None, None)],
)
def test_trip_length_buckets(nights, bucket):
    assert nights_bucket(nights) == bucket


def test_the_minimum_sample_is_enforced_everywhere():
    assert MIN_SAMPLE_FOR_ANY_CLAIM >= 5
    assert summarise(300, [300] * (MIN_SAMPLE_FOR_ANY_CLAIM - 1), "x").available is False
    assert summarise(300, [300] * MIN_SAMPLE_FOR_ANY_CLAIM, "x").available is True


# ------------------------------------------------- attaching history to trips

def _trip(price: float, db_session):
    from datetime import date as _d
    from app.models import TripSearchRequest
    from app.providers.travelpayouts.mapper import RoundTripFare
    from app.services.trip_builder import build_round_trip_options

    ask = TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["JFK"],
        startDate=_d(2026, 9, 1), endDate=_d(2026, 9, 30),
        minTripLengthDays=3, maxTripLengthDays=14, maxBudget=2000,
        maxGroundTransferHours=4, tripStyle="one city",
    )
    fare = RoundTripFare(
        origin="VIE", destination="JFK", price=price, currency="EUR",
        departureDate="2026-09-20", returnDate="2026-09-27",
        observedAt=datetime.utcnow() - timedelta(hours=3),
    )
    return build_round_trip_options([fare], ask, enforce_budget=False)[0]


def test_a_cheap_fare_is_classified_once_enough_history_exists(db_session):
    from app.pricing.history import attach_price_history

    repo = PriceObservationsRepository(db_session)
    repo.record_observations([
        observation(price=price, found_at=datetime(2026, 8, 1) + timedelta(hours=index))
        for index, price in enumerate(
            [389, 421, 405, 367, 438, 410, 351, 395, 462, 415, 382, 447, 359, 401, 430,
             398, 412, 377, 455, 388, 419, 433, 372, 408, 425]
        )
    ])

    trip = _trip(347, db_session)
    attach_price_history(db_session, [trip])

    assert trip.price.history.available is True
    assert trip.price.history.classification in {"exceptional", "great"}
    assert trip.price.history.confidence == "medium"
    assert trip.price.history.sampleCount >= 15


def test_a_composite_total_is_never_classified(db_session):
    """A multi-city sum has no comparable population, so it gets no verdict."""
    from app.pricing.history import attach_price_history

    repo = PriceObservationsRepository(db_session)
    repo.record_observations([
        observation(price=p, found_at=datetime(2026, 8, 1) + timedelta(hours=i))
        for i, p in enumerate(range(350, 400))
    ])

    trip = _trip(347, db_session)
    trip.price.kind = "estimated_multi_city"
    trip.price.isEstimate = True
    attach_price_history(db_session, [trip])

    assert trip.price.history is None


def test_a_broken_history_lookup_does_not_break_the_search(db_session, monkeypatch):
    """History is an enhancement. A search that works beats a search with a badge."""
    from app.tools.base import ToolContext
    from app.tools.registry import build_default_tool_registry
    from app.models import TripSearchRequest

    def explode(*args, **kwargs):
        raise RuntimeError("history database unavailable")

    monkeypatch.setattr(
        "app.db.repositories.price_observations_repository.PriceObservationsRepository.route_observations",
        explode,
    )

    ask = TripSearchRequest(
        originAirports=["VIE"], startDate=date(2026, 10, 1), endDate=date(2026, 10, 31),
        minTripLengthDays=3, maxTripLengthDays=10, maxBudget=800,
        maxGroundTransferHours=4, tripStyle="surprise me",
    )
    result = build_default_tool_registry().run_tool(
        "search_trips", ask, ToolContext(db=db_session, user_id=None)
    )

    # The search completed; trips simply carry no history verdict.
    assert result.trips is not None
    assert all((trip.price is None or trip.price.history is None) for trip in result.trips)


# -------------------------------------------- what may never be compared

def test_one_way_and_round_trip_observations_are_kept_apart(db_session):
    """A one-way fare is not a cheap round trip.

    Pooling them would let a route with many one-ways drag the round-trip
    typical range down, and every round trip on it would then look like a
    bargain against a number that describes a different product.
    """
    repository = PriceObservationsRepository(db_session)
    repository.record_observations(
        [observation(trip_type="return", price=400.0, found_at=FOUND + timedelta(minutes=i))
         for i in range(8)]
        + [observation(trip_type="one_way", return_date=None, price=90.0,
                       found_at=FOUND + timedelta(hours=1, minutes=i))
           for i in range(8)]
    )

    found = repository.route_observations([("VIE", "JFK", "return"), ("VIE", "JFK", "one_way")])

    return_prices = [row[0] for row in found[("VIE", "JFK", "return")]]
    one_way_prices = [row[0] for row in found[("VIE", "JFK", "one_way")]]
    assert set(return_prices) == {400.0}
    assert set(one_way_prices) == {90.0}
    assert not set(return_prices) & set(one_way_prices)


def test_a_route_with_only_one_way_history_yields_no_round_trip_comparison(db_session):
    """The dangerous direction: plenty of evidence, none of it applicable."""
    repository = PriceObservationsRepository(db_session)
    repository.record_observations(
        [observation(trip_type="one_way", return_date=None, price=90.0,
                     found_at=FOUND + timedelta(minutes=i)) for i in range(30)]
    )

    found = repository.route_observations([("VIE", "JFK", "return")])

    assert not found.get(("VIE", "JFK", "return"))


def test_an_open_jaw_total_is_never_measured_against_return_history(db_session):
    """An open-jaw total is two separately observed fares added together.

    Comparing that against single-ticket round-trip history would be comparing
    two different things, so it is excluded from classification entirely rather
    than compared and caveated.
    """
    from app.pricing.history import CLASSIFIABLE_KINDS

    assert "estimated_open_jaw" not in CLASSIFIABLE_KINDS
    assert "estimated_multi_city" not in CLASSIFIABLE_KINDS
    assert CLASSIFIABLE_KINDS == {"cached_return", "cached_one_way"}


def test_observations_never_mix_across_routes(db_session):
    repository = PriceObservationsRepository(db_session)
    repository.record_observations(
        [observation(destination="JFK", price=400.0, found_at=FOUND + timedelta(minutes=i))
         for i in range(6)]
        + [observation(destination="BCN", price=80.0, found_at=FOUND + timedelta(minutes=i))
           for i in range(6)]
    )

    found = repository.route_observations([("VIE", "JFK", "return"), ("VIE", "BCN", "return")])

    assert {row[0] for row in found[("VIE", "JFK", "return")]} == {400.0}
    assert {row[0] for row in found[("VIE", "BCN", "return")]} == {80.0}
