from datetime import date

import pytest

from app.models import TripSearchRequest
from app.services.destination_scope import (
    MAX_COUNTRIES_PER_SCOPE,
    MIN_COUNTRIES_PER_SCOPE,
    countries_that_fit,
    resolve_destination_scope,
)


def make_request(**overrides) -> TripSearchRequest:
    payload = dict(
        originAirports=["VIE"],
        destinationAirports=None,
        destinationCountries=[],
        destinationRegions=[],
        destinationContinents=[],
        excludeEurope=False,
        unvisitedOnly=False,
        returnOriginAirports=None,
        startDate=date(2026, 10, 1),
        endDate=date(2026, 10, 31),
        minTripLengthDays=4,
        maxTripLengthDays=10,
        maxBudget=900,
        maxGroundTransferHours=4,
        tripStyle="surprise me",
        directOnly=False,
    )
    payload.update(overrides)
    return TripSearchRequest(**payload)


def test_no_destination_fields_is_an_anywhere_scope():
    scope = resolve_destination_scope(make_request())

    assert scope.is_anywhere
    assert scope.query_targets == ()
    assert scope.options_per_destination == 1


def test_named_places_become_query_targets():
    scope = resolve_destination_scope(make_request(destinationAirports=["tyo", "DUB"]))

    assert scope.kind == "places"
    assert scope.query_targets == ("TYO", "DUB")
    # A named place is a request to compare its dates.
    assert scope.options_per_destination == 4


def test_a_country_becomes_a_country_query_rather_than_a_filter():
    """The regression this module exists for: 'Ireland' has to reach the provider."""
    scope = resolve_destination_scope(make_request(destinationCountries=["IE"]))

    assert scope.is_targeted
    assert scope.query_targets == ("IE",)


def test_regions_expand_to_their_countries():
    scope = resolve_destination_scope(make_request(destinationRegions=["nordics"]))

    assert set(scope.query_targets) == {"DK", "FI", "IS", "NO", "SE"}
    assert scope.label == "Nordics"


def test_continents_are_narrowed_to_a_bounded_set_of_countries():
    scope = resolve_destination_scope(make_request(destinationContinents=["Asia"]))

    assert scope.is_targeted
    assert 0 < len(scope.query_targets) <= MAX_COUNTRIES_PER_SCOPE
    assert scope.truncated
    assert len(scope.considered_country_codes) > len(scope.query_targets)
    # A continent is a browse, so results should spread across places.
    assert scope.options_per_destination == 2


def test_cached_fare_history_decides_which_countries_are_probed_first():
    scope = resolve_destination_scope(
        make_request(destinationContinents=["Asia"]),
        ranked_country_hint=("TH", "GE"),
    )

    assert scope.query_targets[:2] == ("TH", "GE")


def test_outside_europe_alone_is_a_destination_wish_not_a_filter():
    scope = resolve_destination_scope(make_request(excludeEurope=True))

    assert scope.is_targeted
    assert scope.query_targets
    assert not any(code in {"ES", "IT", "FR", "DE"} for code in scope.query_targets)


def test_outside_europe_drops_european_countries_from_a_wider_scope():
    scope = resolve_destination_scope(
        make_request(destinationCountries=["ES", "JP"], excludeEurope=True)
    )

    assert scope.query_targets == ("JP",)


@pytest.mark.parametrize(
    ("origins", "budget", "expected"),
    [
        (1, 30, MAX_COUNTRIES_PER_SCOPE),
        (6, 30, 5),
        (20, 30, MIN_COUNTRIES_PER_SCOPE),
    ],
)
def test_country_breadth_is_bounded_by_the_request_budget(origins, budget, expected):
    assert countries_that_fit(origins, budget) == expected


def test_more_origins_means_fewer_countries_probed():
    one_origin = resolve_destination_scope(make_request(destinationContinents=["Africa"]))
    many_origins = resolve_destination_scope(
        make_request(originAirports=["VIE", "BUD", "LJU", "ZAG", "TRS", "VCE"], destinationContinents=["Africa"])
    )

    assert len(many_origins.query_targets) < len(one_origin.query_targets)


def test_unknown_country_codes_are_ignored_rather_than_queried():
    scope = resolve_destination_scope(make_request(destinationCountries=["ZZ"]))

    assert scope.is_anywhere
