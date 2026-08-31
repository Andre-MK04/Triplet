"""Multi-city and open-jaw itineraries: every hop priced, dates chosen together.

The thing worth testing here is that dates are chosen for the whole trip at once.
A greedy leg-by-leg choice takes the cheapest first flight and can then be forced
onto an expensive last one; the total is what matters.
"""

from datetime import date

import pytest

from app.models import TripSearchRequest
from app.providers.travelpayouts.mapper import OneWayFare
from app.services.itinerary_builder import (
    build_itineraries,
    flight_legs,
    plan_route,
)


def request(**overrides) -> TripSearchRequest:
    values = dict(
        originAirports=["VIE"],
        startDate=date(2026, 10, 1),
        endDate=date(2026, 10, 10),
        minTripLengthDays=4,
        maxTripLengthDays=14,
        maxBudget=1000,
        maxGroundTransferHours=6,
        tripStyle="surprise me",
        tripPlan="multi_city",
        routeStops=["BCN", "LIS"],
    )
    values.update(overrides)
    return TripSearchRequest(**values)


def fare(origin, destination, day, price) -> OneWayFare:
    return OneWayFare(
        origin=origin, destination=destination,
        departureDate=f"2026-10-{day:02d}", price=price, currency="EUR", stops=0,
    )


def spread(origin, destination, price, days=range(1, 26)) -> list[OneWayFare]:
    return [fare(origin, destination, day, price) for day in days]


def test_multi_city_route_is_home_then_each_stop_then_home():
    legs = plan_route(request(), "VIE")

    assert [(leg.origin, leg.destination) for leg in legs] == [
        ("VIE", "BCN"), ("BCN", "LIS"), ("LIS", "VIE"),
    ]
    assert not any(leg.is_ground for leg in legs)
    assert flight_legs(legs) == [("VIE", "BCN"), ("BCN", "LIS"), ("LIS", "VIE")]


def test_open_jaw_flies_in_to_one_city_and_home_from_another():
    legs = plan_route(
        request(tripPlan="open_jaw", routeStops=None,
                destinationAirports=["STO"], returnOriginAirports=["HEL"]),
        "BUD",
    )

    assert [(leg.origin, leg.destination) for leg in legs] == [
        ("BUD", "STO"), ("STO", "HEL"), ("HEL", "BUD"),
    ]
    # The crossing between the two cities is the traveller's own problem to make.
    assert [leg.is_ground for leg in legs] == [False, True, False]
    assert flight_legs(legs) == [("BUD", "STO"), ("HEL", "BUD")]


def test_a_plain_return_trip_is_not_an_itinerary():
    assert plan_route(request(tripPlan="return", routeStops=None), "VIE") is None


def test_nearby_stops_become_a_ground_hop_rather_than_a_flight():
    legs = plan_route(request(routeStops=["VCE", "TRS"]), "VIE")

    # Venice to Trieste is under 400 km; nobody flies it.
    assert [leg.is_ground for leg in legs] == [False, True, False]


def test_a_stop_that_repeats_the_home_airport_is_rejected():
    assert plan_route(request(routeStops=["BCN", "VIE"]), "VIE") is None


def test_total_is_the_sum_of_every_flown_hop():
    legs = plan_route(request(), "VIE")
    fares = {
        ("VIE", "BCN"): spread("VIE", "BCN", 50),
        ("BCN", "LIS"): spread("BCN", "LIS", 30),
        ("LIS", "VIE"): spread("LIS", "VIE", 70),
    }

    trip = build_itineraries(request(), "VIE", legs, fares)[0]

    assert trip.totalPrice == 150
    assert trip.flightCost == 150
    assert len([s for s in trip.segments if s.kind == "flight"]) == 3


def test_dates_are_chosen_for_the_cheapest_whole_trip_not_the_cheapest_first_hop():
    """A cheap first flight that forces an expensive last one must lose.

    Leaving on the 1st costs EUR 10 instead of EUR 60, but an eight-day ceiling
    then puts the cheap way home out of reach and the trip ends up at EUR 540.
    """
    ask = request(minTripLengthDays=4, maxTripLengthDays=8)
    legs = plan_route(ask, "VIE")
    fares = {
        ("VIE", "BCN"): [fare("VIE", "BCN", 1, 10), fare("VIE", "BCN", 5, 60)],
        ("BCN", "LIS"): spread("BCN", "LIS", 30, days=[3, 7]),
        ("LIS", "VIE"): [fare("LIS", "VIE", 7, 500), fare("LIS", "VIE", 11, 40)],
    }

    trip = build_itineraries(ask, "VIE", legs, fares)[0]

    assert trip.outboundFlight.departureDateTime.date() == date(2026, 10, 5)
    assert trip.totalPrice == 130  # 60 + 30 + 40, not 10 + 30 + 500


def test_ground_hops_are_described_but_never_priced_into_the_total():
    legs = plan_route(
        request(tripPlan="open_jaw", routeStops=None,
                destinationAirports=["STO"], returnOriginAirports=["HEL"]),
        "BUD",
    )
    fares = {
        ("BUD", "STO"): spread("BUD", "STO", 80),
        ("HEL", "BUD"): spread("HEL", "BUD", 90),
    }

    trip = build_itineraries(
        request(tripPlan="open_jaw", routeStops=None,
                destinationAirports=["STO"], returnOriginAirports=["HEL"]),
        "BUD", legs, fares,
    )[0]

    ground = [s for s in trip.segments if s.kind == "ground"]
    assert len(ground) == 1
    assert ground[0].transfer.estimatedCost > 0
    assert trip.groundEstimate == ground[0].transfer.estimatedCost
    # Flights only.
    assert trip.totalPrice == 170
    assert trip.flightCost == 170


def test_an_unpriceable_hop_yields_no_itinerary_rather_than_a_guess():
    legs = plan_route(request(), "VIE")
    fares = {
        ("VIE", "BCN"): spread("VIE", "BCN", 50),
        ("BCN", "LIS"): [],  # nothing on offer
        ("LIS", "VIE"): spread("LIS", "VIE", 70),
    }

    assert build_itineraries(request(), "VIE", legs, fares) == []


def test_itineraries_respect_the_requested_trip_length():
    legs = plan_route(request(minTripLengthDays=6, maxTripLengthDays=8), "VIE")
    fares = {
        ("VIE", "BCN"): spread("VIE", "BCN", 50),
        ("BCN", "LIS"): spread("BCN", "LIS", 30),
        ("LIS", "VIE"): spread("LIS", "VIE", 70),
    }

    trips = build_itineraries(request(minTripLengthDays=6, maxTripLengthDays=8), "VIE", legs, fares)

    assert trips
    assert all(6 <= trip.nights <= 8 for trip in trips)


def test_stays_record_where_the_traveller_sleeps_and_for_how_long():
    legs = plan_route(request(minTripLengthDays=6, maxTripLengthDays=8), "VIE")
    fares = {
        ("VIE", "BCN"): spread("VIE", "BCN", 50),
        ("BCN", "LIS"): spread("BCN", "LIS", 30),
        ("LIS", "VIE"): spread("LIS", "VIE", 70),
    }

    trip = build_itineraries(request(minTripLengthDays=6, maxTripLengthDays=8), "VIE", legs, fares)[0]

    assert [stay.code for stay in trip.stays] == ["BCN", "LIS"]
    assert sum(stay.nights for stay in trip.stays) == trip.nights
    assert all(stay.nights >= 1 for stay in trip.stays)


def test_direct_only_drops_fares_with_stops():
    legs = plan_route(request(directOnly=True), "VIE")
    connecting = OneWayFare(
        origin="BCN", destination="LIS", departureDate="2026-10-06", price=5, stops=1,
    )
    fares = {
        ("VIE", "BCN"): spread("VIE", "BCN", 50),
        ("BCN", "LIS"): [connecting],
        ("LIS", "VIE"): spread("LIS", "VIE", 70),
    }

    assert build_itineraries(request(directOnly=True), "VIE", legs, fares) == []
