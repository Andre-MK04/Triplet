from datetime import date

from app.db.seed import FLIGHTS
from app.models import Flight, GroundTransfer, TripOption, TripSearchRequest
from app.services.trip_scoring import calculate_trip_score


def request(**overrides) -> TripSearchRequest:
    values = {
        "originAirports": ["VIE"],
        "startDate": date(2026, 7, 1),
        "endDate": date(2026, 8, 31),
        "minTripLengthDays": 1,
        "maxTripLengthDays": 12,
        "maxBudget": 200,
        "maxGroundTransferHours": 5,
        "tripStyle": "surprise me",
    }
    values.update(overrides)
    return TripSearchRequest(**values)


def flight(flight_id: str):
    item = next(row for row in FLIGHTS if row[0] == flight_id)
    return Flight(
        id=item[0],
        origin=item[1],
        destination=item[2],
        departureDateTime=item[3],
        arrivalDateTime=item[4],
        airline=item[5],
        price=item[6],
        baggageIncluded=item[7],
    )


def transfer(duration: float = 2.0) -> GroundTransfer:
    return GroundTransfer(
        fromAirport="ALC",
        toAirport="VLC",
        fromCity="Alicante",
        toCity="Valencia",
        durationHours=duration,
        estimatedCost=20,
        mode="train/bus",
    )


def trip(**overrides) -> TripOption:
    values = {
        "id": "test-trip",
        "tripType": "same_city",
        "outboundFlight": flight("f004"),
        "returnFlight": flight("f005"),
        "groundTransfer": None,
        "totalPrice": 100,
        "tripLengthDays": 6,
        "nights": 6,
        "score": 0,
        "explanation": "",
        "warnings": [],
        "tags": [],
    }
    values.update(overrides)
    return TripOption(**values)


def test_cheaper_trips_score_higher_than_expensive_trips():
    cheap = trip(totalPrice=70)
    expensive = trip(totalPrice=170)

    assert calculate_trip_score(cheap, request()) > calculate_trip_score(expensive, request())


def test_long_ground_transfers_reduce_score():
    easy = trip(tripType="open_jaw", groundTransfer=transfer(2), totalPrice=120)
    long = trip(tripType="open_jaw", groundTransfer=transfer(4.5), totalPrice=120)

    assert calculate_trip_score(easy, request()) > calculate_trip_score(long, request())


def test_early_and_late_flights_reduce_score():
    clean = trip(outboundFlight=flight("f004"), returnFlight=flight("f005"))
    awkward = trip(outboundFlight=flight("f025"), returnFlight=flight("f026"))

    assert calculate_trip_score(clean, request()) > calculate_trip_score(awkward, request())


def test_open_jaw_with_easy_transfer_can_receive_small_bonus():
    same_city = trip(totalPrice=90)
    open_jaw = trip(tripType="open_jaw", groundTransfer=transfer(2), totalPrice=90)

    assert calculate_trip_score(open_jaw, request()) == calculate_trip_score(same_city, request())


def test_score_is_capped_between_zero_and_100():
    very_good = trip(totalPrice=10, tripType="open_jaw", groundTransfer=transfer(2))
    very_bad = trip(
        totalPrice=200,
        tripType="open_jaw",
        groundTransfer=transfer(9),
        nights=1,
        outboundFlight=flight("f025"),
        returnFlight=flight("f026"),
    )

    assert 0 <= calculate_trip_score(very_good, request()) <= 100
    assert 0 <= calculate_trip_score(very_bad, request(includeBaggage=True)) <= 100
