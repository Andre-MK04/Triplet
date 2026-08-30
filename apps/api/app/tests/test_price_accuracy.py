"""What Triplet quotes, and what it claims about that quote.

Travelpayouts serves cached market fares. We cannot make a cached number equal a
live one, but we can stop three avoidable mismatches: quoting in a currency the
booking page will not use, claiming a days-old fare was seen just now, and
sending people to a fresh search instead of the fare we quoted.
"""

from datetime import date, datetime

from app.providers.travelpayouts.affiliate_links import ItinerarySegment, build_aviasales_itinerary_url
from app.providers.travelpayouts.mapper import (
    build_search_link,
    map_price_calendar_response,
    map_round_trip_rows,
    observed_at_from_link,
)
from app.models import TripSearchRequest
from app.providers.travelpayouts.mapper import RoundTripFare
from app.services.trip_builder import build_round_trip_options


PROVIDER_LINK = (
    "/search/VIE3009BCN03101?t=FR179074890017907576&search_date=28082026"
    "&expected_price_currency=eur&expected_price=90"
)


def round_trip_payload():
    return {
        "currency": "eur",
        "data": [
            {
                "origin": "VIE",
                "destination": "BCN",
                "departure_at": "2026-09-30T06:15:00+02:00",
                "return_at": "2026-10-03T11:45:00+02:00",
                "price": 90,
                "airline": "FR",
                "transfers": 0,
                "link": PROVIDER_LINK,
            }
        ],
    }


def test_booking_links_carry_our_currency():
    link = build_search_link(PROVIDER_LINK, marker="747408")

    assert "currency=eur" in link
    assert "marker=747408" in link


def test_constructed_search_links_carry_our_currency():
    url = build_aviasales_itinerary_url(
        [
            ItinerarySegment("VIE", "BCN", date(2026, 9, 30)),
            ItinerarySegment("BCN", "VIE", date(2026, 10, 3)),
        ],
        marker="747408",
    )

    assert "currency=eur" in url


def test_observation_time_comes_from_the_provider_not_from_now():
    assert observed_at_from_link(PROVIDER_LINK) == datetime(2026, 8, 28)
    assert observed_at_from_link("/search/x?t=abc") is None
    assert observed_at_from_link(None) is None


def test_round_trip_fares_report_when_the_provider_saw_the_price():
    fare = map_round_trip_rows(round_trip_payload(), marker=None)[0]

    # Not "now": this fare was found on 28 August.
    assert fare.observedAt == datetime(2026, 8, 28)


def test_calendar_fares_admit_they_have_no_sighting_time():
    payload = {
        "currency": "eur",
        "data": {
            "2026-09-30": {
                "origin": "VIE",
                "destination": "BCN",
                "departure_at": "2026-09-30T06:15:00+02:00",
                "return_at": "2026-10-03T11:45:00+02:00",
                "price": 95,
                "airline": "FR",
                "transfers": 0,
            }
        },
    }

    fare = map_price_calendar_response(payload, "VIE", "BCN", marker=None)[0]

    # The calendar carries no link and therefore no sighting date. Saying nothing
    # is correct; inventing "just now" is what this replaced.
    assert fare.observedAt is None
    assert fare.departureDate == "2026-09-30"
    assert fare.returnDate == "2026-10-03"


def test_trip_links_to_the_exact_fare_when_the_provider_gave_one():
    fare = RoundTripFare(
        origin="VIE", destination="BCN", price=90, currency="EUR",
        departureDate="2026-09-30", returnDate="2026-10-03",
        bookingUrl="https://www.aviasales.com/search/VIE3009BCN03101?t=abc&currency=eur",
    )
    request = TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["BCN"],
        startDate=date(2026, 9, 1), endDate=date(2026, 10, 1),
        minTripLengthDays=1, maxTripLengthDays=10, maxBudget=600,
        maxGroundTransferHours=4, tripStyle="one city",
    )

    trip = build_round_trip_options([fare], request, enforce_budget=False)[0]

    # The fare's own link, not a fresh search that could surface a different trip.
    assert trip.bookingUrl == fare.bookingUrl


def test_trip_falls_back_to_a_route_and_date_search_without_a_provider_link():
    fare = RoundTripFare(
        origin="VIE", destination="BCN", price=95, currency="EUR",
        departureDate="2026-09-30", returnDate="2026-10-03",
    )
    request = TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["BCN"],
        startDate=date(2026, 9, 1), endDate=date(2026, 10, 1),
        minTripLengthDays=1, maxTripLengthDays=10, maxBudget=600,
        maxGroundTransferHours=4, tripStyle="one city",
    )

    trip = build_round_trip_options([fare], request, enforce_budget=False)[0]

    assert trip.bookingUrl and "2026-09-30" in trip.bookingUrl
    assert "currency=eur" in trip.bookingUrl
