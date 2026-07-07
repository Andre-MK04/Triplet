from datetime import date

from app.models import TripSearchRequest
from app.services.trip_builder import build_trips


def default_request(**overrides) -> TripSearchRequest:
    values = {
        "originAirports": ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"],
        "startDate": date(2026, 7, 1),
        "endDate": date(2026, 8, 31),
        "minTripLengthDays": 4,
        "maxTripLengthDays": 8,
        "maxBudget": 180,
        "maxGroundTransferHours": 4,
        "tripStyle": "surprise me",
    }
    values.update(overrides)
    return TripSearchRequest(**values)


def test_creates_valid_same_city_trips(trip_data):
    trips = build_trips(default_request(tripStyle="one city"), **trip_data)

    assert trips
    assert all(trip.tripType == "same_city" for trip in trips)
    assert any(trip.outboundFlight.destination == trip.returnFlight.origin for trip in trips)


def test_creates_valid_open_jaw_trips(trip_data):
    trips = build_trips(default_request(tripStyle="two nearby cities"), **trip_data)

    assert trips
    assert all(trip.tripType == "open_jaw" for trip in trips)
    assert all(trip.groundTransfer is not None for trip in trips)
    assert any(
        trip.outboundFlight.destination == "ALC" and trip.returnFlight.origin == "VLC"
        for trip in trips
    )


def test_does_not_create_trips_over_max_budget(trip_data):
    max_budget = 95
    trips = build_trips(default_request(maxBudget=max_budget), **trip_data)

    assert trips
    assert all(trip.totalPrice <= max_budget for trip in trips)


def test_does_not_create_trips_outside_trip_length_range(trip_data):
    trips = build_trips(default_request(minTripLengthDays=6, maxTripLengthDays=6), **trip_data)

    assert trips
    assert all(trip.nights == 6 for trip in trips)


def test_does_not_create_open_jaw_trips_without_known_ground_transfer(trip_data):
    trips = build_trips(default_request(originAirports=["VIE"], tripStyle="two nearby cities"), **trip_data)

    assert all(trip.groundTransfer is not None for trip in trips)
    assert not any(
        trip.outboundFlight.destination == "MAD" and trip.returnFlight.origin == "ALC"
        for trip in trips
    )


def test_respects_max_ground_transfer_hours(trip_data):
    trips = build_trips(default_request(tripStyle="two nearby cities", maxGroundTransferHours=2), **trip_data)

    assert trips
    assert all(trip.groundTransfer.durationHours <= 2 for trip in trips if trip.groundTransfer)


def test_sorts_by_score_descending(trip_data):
    trips = build_trips(default_request(), **trip_data)
    scores = [trip.score for trip in trips]

    assert trips
    assert scores == sorted(scores, reverse=True)


def test_destination_filter_restricts_outbound_destinations(trip_data):
    # With a destination filter, every outbound leg must land in the requested set.
    trips = build_trips(
        default_request(destinationAirports=["ALC"], tripStyle="one city"),
        **trip_data,
    )

    assert trips
    assert all(trip.outboundFlight.destination == "ALC" for trip in trips)


def test_destination_filter_excludes_other_destinations(trip_data):
    # A destination we have no seeded flights to must yield no trips, not fall
    # back to showing unrelated cities.
    trips = build_trips(
        default_request(destinationAirports=["CPH"], tripStyle="one city"),
        **trip_data,
    )

    assert trips == []
