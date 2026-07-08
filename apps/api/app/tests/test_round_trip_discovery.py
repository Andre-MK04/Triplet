from datetime import date

from app.models import TripSearchRequest
from app.providers.travelpayouts.mapper import RoundTripFare, map_city_directions_response
from app.services.trip_builder import build_round_trip_options, merge_trip_options


def request(**overrides) -> TripSearchRequest:
    values = dict(
        originAirports=["VIE"],
        startDate=date(2026, 8, 1),
        endDate=date(2026, 8, 31),
        minTripLengthDays=3,
        maxTripLengthDays=10,
        maxBudget=300,
        maxGroundTransferHours=4,
        tripStyle="surprise me",
    )
    values.update(overrides)
    return TripSearchRequest(**values)


def city_directions_payload():
    return {
        "success": True,
        "currency": "eur",
        "data": {
            "CPH": {"origin": "VIE", "destination": "CPH", "price": 118, "airline": "SK",
                    "transfers": 0, "departure_at": "2026-08-05T09:00:00+02:00",
                    "return_at": "2026-08-10T18:00:00+02:00", "link": "/search/x"},
            "MOW": {"origin": "VIE", "destination": "MOW", "price": 90, "airline": "SU",
                    "transfers": 1, "departure_at": "2026-08-06T09:00:00+02:00",
                    "return_at": "2026-08-11T18:00:00+02:00", "link": "/search/y"},
            "BCN": {"origin": "VIE", "destination": "BCN", "price": 70, "airline": "VY",
                    "transfers": 0, "departure_at": "2026-09-20T09:00:00+02:00",
                    "return_at": "2026-09-25T18:00:00+02:00", "link": "/search/z"},
        },
    }


def test_city_directions_mapper_extracts_round_trips():
    fares = map_city_directions_response(city_directions_payload(), "VIE", marker="m1")
    by_dest = {f.destination: f for f in fares}
    assert by_dest["CPH"].price == 118
    assert by_dest["CPH"].affiliateUrl and "marker=m1" in by_dest["CPH"].affiliateUrl


def test_build_round_trips_filters_europe_budget_and_date_window():
    fares = map_city_directions_response(city_directions_payload(), "VIE", marker=None)
    trips = build_round_trip_options(fares, request(), scoring=None)
    dests = {t.outboundFlight.destination for t in trips}
    # CPH kept; MOW dropped (non-European); BCN dropped (September, outside August window).
    assert "CPH" in dests
    assert "MOW" not in dests
    assert "BCN" not in dests
    cph = next(t for t in trips if t.outboundFlight.destination == "CPH")
    assert cph.fareKind == "round_trip_bundle"
    assert cph.totalPrice == 118


def test_build_round_trips_respects_destination_scope():
    fares = map_city_directions_response(city_directions_payload(), "VIE", marker=None)
    # Scope to Sweden only -> Copenhagen (Denmark) must be excluded.
    trips = build_round_trip_options(fares, request(destinationAirports=["ARN", "GOT"]), scoring=None)
    assert trips == []


def test_merge_prefers_cheaper_bundle_for_same_route():
    from app.services.trip_builder import build_round_trip_options as brt
    fares = [RoundTripFare(origin="VIE", destination="CPH", price=99, currency="EUR",
                           departureDate="2026-08-05", returnDate="2026-08-09", airline="SK",
                           bookingUrl="/x")]
    bundles = brt(fares, request(), scoring=None)
    # A pricier paired trip on the same route should lose to the 99 bundle.
    paired = []
    merged = merge_trip_options(paired, bundles)
    assert len(merged) == 1 and merged[0].totalPrice == 99
