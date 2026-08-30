"""Worldwide destination search: a named country must reach the provider.

Before these behaviours existed, "Ireland", "the Nordics", "Asia" and "outside
Europe" were filters applied to a small per-origin discovery cache, so any place
the cache did not already hold returned nothing at all.
"""

from datetime import date

import pytest

from app.models import TripSearchRequest
from app.providers.flight_provider import DateRange
from app.providers.travelpayouts.flight_provider import plan_route_queries
from app.providers.travelpayouts.mapper import RoundTripFare
from app.services.flight_search_service import FlightSearchService
from app.services.trip_builder import build_round_trip_options, merge_trip_options
from app.tools.base import ToolContext
from app.tools.registry import build_default_tool_registry
from app.tools.travel_tools import UnsupportedFlightPlaceError


def request(**overrides) -> TripSearchRequest:
    values = dict(
        originAirports=["VIE"],
        startDate=date(2026, 10, 1),
        endDate=date(2026, 10, 31),
        minTripLengthDays=4,
        maxTripLengthDays=14,
        maxBudget=1200,
        maxGroundTransferHours=4,
        tripStyle="surprise me",
    )
    values.update(overrides)
    return TripSearchRequest(**values)


class RecordingProvider:
    """Stands in for the live provider and records what it was asked about."""

    name = "travelpayouts"

    def __init__(self, fares_by_destination: dict[str, list[RoundTripFare]] | None = None):
        self.fares_by_destination = fares_by_destination or {}
        self.round_trip_calls: list[tuple[list[str], list[str]]] = []
        self.discover_calls: list[list[str]] = []
        self.in_window_calls: list[list[str]] = []

    def round_trips_for(self, origins, destinations, date_range, direct_only=False):
        self.round_trip_calls.append((list(origins), list(destinations)))
        fares: list[RoundTripFare] = []
        for destination in destinations:
            fares.extend(self.fares_by_destination.get(destination, []))
        return fares

    def discover_round_trips(self, origins):
        self.discover_calls.append(list(origins))
        return []

    def round_trips_in_window(self, origins, date_range):
        self.in_window_calls.append(list(origins))
        return []


def fare(destination: str, price: float = 480.0) -> RoundTripFare:
    return RoundTripFare(
        origin="VIE",
        destination=destination,
        price=price,
        currency="EUR",
        departureDate="2026-10-06",
        returnDate="2026-10-14",
        airline="LH",
        bookingUrl="/search/x",
    )


def test_a_country_scope_asks_the_provider_about_that_country():
    provider = RecordingProvider({"JP": [fare("TYO", 820), fare("OSA", 870)]})
    service = FlightSearchService(provider_name="travelpayouts", provider=provider)

    fares = service.discover_round_trip_fares(request(destinationCountries=["JP"]))

    assert provider.round_trip_calls == [(["VIE"], ["JP"])]
    assert {row.destination for row in fares} == {"TYO", "OSA"}
    assert provider.discover_calls == []


def test_a_region_scope_asks_about_each_of_its_countries():
    provider = RecordingProvider()
    service = FlightSearchService(provider_name="travelpayouts", provider=provider)

    service.discover_round_trip_fares(request(destinationRegions=["nordics"]))

    _, destinations = provider.round_trip_calls[0]
    assert set(destinations) == {"DK", "FI", "IS", "NO", "SE"}


def test_outside_europe_asks_about_non_european_countries():
    provider = RecordingProvider()
    service = FlightSearchService(provider_name="travelpayouts", provider=provider)

    service.discover_round_trip_fares(request(excludeEurope=True))

    _, destinations = provider.round_trip_calls[0]
    assert destinations
    assert not any(code in {"ES", "IT", "FR", "GR"} for code in destinations)


def test_an_anywhere_search_asks_for_fares_inside_its_own_date_window():
    provider = RecordingProvider()
    service = FlightSearchService(provider_name="travelpayouts", provider=provider)

    service.discover_round_trip_fares(request())

    assert provider.round_trip_calls == []
    assert provider.in_window_calls == [["VIE"]]


def test_provider_results_outside_the_requested_country_are_still_filtered_out():
    # A country query should only ever answer with that country; if a provider
    # returns something else, it must not leak into the results.
    provider = RecordingProvider({"IE": [fare("DUB", 86), fare("BCN", 70)]})
    service = FlightSearchService(provider_name="travelpayouts", provider=provider)

    fares = service.discover_round_trip_fares(request(destinationCountries=["IE"]))

    assert [row.destination for row in fares] == ["DUB"]


def test_query_plan_covers_every_destination_before_going_deeper():
    plan = plan_route_queries(
        ["VIE", "BUD"],
        ["JP", "TH", "VN"],
        DateRange(start=date(2026, 10, 1), end=date(2026, 11, 30)),
    )

    # First origin, first month: every requested destination.
    assert [destination for _, destination, _ in plan[:3]] == ["JP", "TH", "VN"]
    # Truncating to the first origin still covers all three destinations.
    assert {destination for _, destination, _ in plan[:3]} == {"JP", "TH", "VN"}
    assert plan[0][2] == "2026-10" and plan[-1][2] == "2026-11"


def test_an_origin_never_queries_itself_as_a_destination():
    plan = plan_route_queries(
        ["VIE"],
        ["VIE", "JP"],
        DateRange(start=date(2026, 10, 1), end=date(2026, 10, 31)),
    )

    assert [destination for _, destination, _ in plan] == ["JP"]


def test_named_destination_keeps_several_dates_but_anywhere_keeps_variety():
    fares = [
        RoundTripFare(origin="VIE", destination="TYO", price=price, currency="EUR",
                      departureDate=departure, returnDate=arrival, airline="LH")
        for price, departure, arrival in [
            (820, "2026-10-04", "2026-10-14"),
            (840, "2026-10-06", "2026-10-16"),
            (860, "2026-10-08", "2026-10-18"),
        ]
    ]
    bundles = build_round_trip_options(fares, request(destinationAirports=["TYO"]), scoring=None)

    assert len(merge_trip_options([], bundles, per_destination_limit=4)) == 3
    assert len(merge_trip_options([], bundles, per_destination_limit=1)) == 1


def test_european_airports_beyond_the_seeded_set_are_valid_origins(db_session):
    registry = build_default_tool_registry()
    context = ToolContext(db=db_session, user_id=None)

    result = registry.run_tool("search_trips", request(originAirports=["MUC"]), context)

    assert result.trips == [] or all(t.outboundFlight.origin == "MUC" for t in result.trips)


def test_non_european_origins_are_rejected(db_session):
    registry = build_default_tool_registry()
    context = ToolContext(db=db_session, user_id=None)

    with pytest.raises(UnsupportedFlightPlaceError, match="JFK"):
        registry.run_tool("search_trips", request(originAirports=["JFK"]), context)
