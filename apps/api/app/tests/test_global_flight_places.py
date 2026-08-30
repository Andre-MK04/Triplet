from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.data.flight_places import catalogue, get_place, is_flightable_place, search_places
from app.deals.refresher import valid_discovery_fares
from app.main import app
from app.models import Flight, TripSearchRequest
from app.providers.flight_provider import DateRange
from app.providers.travelpayouts.affiliate_links import ItinerarySegment, build_aviasales_itinerary_url
from app.providers.travelpayouts.flight_provider import TravelpayoutsAviasalesProvider
from app.providers.travelpayouts.mapper import RoundTripFare
from app.services.trip_builder import build_trips
from app.services.trip_builder import build_round_trip_options
from app.services.trip_scoring import ScoringContext


def test_generated_catalogue_contains_global_flightable_places_and_aliases():
    assert len(catalogue().places) > 7000
    assert all(place.kind in {"airport", "city"} and place.flightable for place in catalogue().places)
    assert get_place("JFK").country_code == "US"
    assert get_place("NYC").kind == "city"
    assert get_place("FRU").code == "BSZ"
    assert is_flightable_place("BCN")
    assert not is_flightable_place("XXX")
    assert search_places("New York", 3)[0].code == "NYC"


def test_global_autocomplete_distinguishes_country_city_and_airport():
    client = TestClient(app)
    japan = client.get("/places/search", params={"q": "Japan"})
    new_york = client.get("/places/search", params={"q": "New York"})
    jfk = client.get("/places/search", params={"q": "JFK"})

    assert japan.status_code == new_york.status_code == jfk.status_code == 200
    assert any(row["kind"] == "country" and row["code"] == "JP" for row in japan.json())
    assert any(row["kind"] == "city" and row["code"] == "NYC" for row in new_york.json())
    assert any(row["kind"] == "airport" and row["code"] == "JFK" for row in jfk.json())
    assert all(len(row["searchCodes"]) <= 20 for row in japan.json())


def test_refresher_validation_keeps_worldwide_fares_and_rejects_unknown_rows():
    fares = [
        RoundTripFare(origin="VIE", destination="JFK", price=500, departureDate="2026-10-01", returnDate="2026-10-10"),
        RoundTripFare(origin="VIE", destination="BCN", price=100, departureDate="2026-10-01", returnDate="2026-10-05"),
        RoundTripFare(origin="VIE", destination="XXX", price=50, departureDate="2026-10-01", returnDate="2026-10-05"),
        RoundTripFare(origin="VIE", destination="VIE", price=20, departureDate="2026-10-01", returnDate="2026-10-05"),
    ]
    assert {fare.destination for fare in valid_discovery_fares(fares)} == {"JFK", "BCN"}


def test_anywhere_provider_does_not_expand_to_route_matrix(monkeypatch):
    class NoRouteClient:
        def prices_for_dates(self, *args, **kwargs):
            raise AssertionError("broad discovery must not call the route API")

    monkeypatch.setattr("app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_enabled", True)
    provider = TravelpayoutsAviasalesProvider(client=NoRouteClient(), cache_enabled=False)
    flights = provider.search_flexible(["VIE"], None, DateRange(start=date(2026, 10, 1), end=date(2026, 10, 31)))
    assert flights == []
    assert provider.requests_attempted == 0


def test_discovery_uses_one_request_per_origin(monkeypatch):
    class DiscoveryClient:
        def __init__(self):
            self.origins = []

        def city_directions(self, origin):
            self.origins.append(origin)
            return {"currency": "eur", "data": {"JFK": {"price": 500, "departure_at": "2026-10-01", "return_at": "2026-10-10"}}}

    monkeypatch.setattr("app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_enabled", True)
    client = DiscoveryClient()
    provider = TravelpayoutsAviasalesProvider(client=client, cache_enabled=False)
    provider.discover_round_trips(["VIE", "ZAG"])
    assert client.origins == ["VIE", "ZAG"]
    assert provider.requests_attempted == 2


def test_explicit_worldwide_route_uses_bounded_targeted_round_trip_queries(monkeypatch):
    class TargetedClient:
        def __init__(self):
            self.calls = []
            self.calendar_calls = []

        def prices_for_dates(self, origin, destination, month, **kwargs):
            self.calls.append((origin, destination, month, kwargs))
            return {
                "currency": "eur",
                "data": [{
                    "origin": origin,
                    "destination": destination,
                    "departure_at": f"{month}-05T09:00:00",
                    "return_at": f"{month}-14T09:00:00",
                    "price": 520,
                }],
            }

        def price_calendar(self, origin, destination, month):
            self.calendar_calls.append((origin, destination, month))
            return {
                "currency": "eur",
                "data": {
                    f"{month}-07": {
                        "origin": origin,
                        "destination": destination,
                        "departure_at": f"{month}-07T09:00:00",
                        "return_at": f"{month}-14T09:00:00",
                        "price": 505,
                        "airline": "LH",
                        "transfers": 1,
                    }
                },
            }

    monkeypatch.setattr("app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_enabled", True)
    client = TargetedClient()
    provider = TravelpayoutsAviasalesProvider(client=client, cache_enabled=False, max_requests=10)
    fares = provider.round_trips_for(
        ["VIE"], ["NYC"], DateRange(start=date(2026, 10, 1), end=date(2026, 11, 30))
    )
    assert len(client.calls) == 2
    assert {(origin, destination) for origin, destination, _, _ in client.calls} == {("VIE", "NYC")}
    assert all(call[3]["one_way"] is False for call in client.calls)
    # A named city is also asked for its price calendar, which is the only source
    # dense enough to cover every trip length on a route.
    assert client.calendar_calls == [("VIE", "NYC", "2026-10"), ("VIE", "NYC", "2026-11")]
    assert {fare.departureDate for fare in fares} == {
        "2026-10-05", "2026-10-07", "2026-11-05", "2026-11-07",
    }


def test_global_round_trip_builds_metadata_link_and_preserves_price_honesty(monkeypatch):
    monkeypatch.setattr("app.providers.travelpayouts.affiliate_links.settings.travelpayouts_marker", "triplet")
    fare = RoundTripFare(
        origin="VIE", destination="JFK", price=520, currency="EUR",
        departureDate="2026-10-01", returnDate="2026-10-10", stops=1,
        observedAt=datetime(2026, 9, 30, 12), expiresAt=datetime(2026, 10, 1, 12),
    )
    request = TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["JFK"],
        startDate=date(2026, 10, 1), endDate=date(2026, 10, 5),
        minTripLengthDays=7, maxTripLengthDays=14, maxBudget=700,
        maxGroundTransferHours=4, tripStyle="one city",
    )
    trip = build_round_trip_options([fare], request)[0]
    assert trip.tripType == "same_city"
    assert trip.fareKind == "round_trip_bundle"
    assert trip.totalPrice == 520
    assert trip.destination.countryCode == "US"
    assert trip.outboundFlight.confidenceLevel == "indicative"
    assert trip.outboundFlight.observedAt == fare.observedAt
    assert "segments%5B1%5D%5Borigin_iata%5D=JFK" in trip.bookingUrl


def test_wishlist_changes_fit_but_not_deal_score():
    fare = RoundTripFare(
        origin="VIE", destination="JFK", price=520,
        departureDate="2026-10-01", returnDate="2026-10-10",
    )
    request = TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["JFK"],
        startDate=date(2026, 10, 1), endDate=date(2026, 10, 5),
        minTripLengthDays=7, maxTripLengthDays=14, maxBudget=700,
        maxGroundTransferHours=4, tripStyle="one city",
    )
    plain = build_round_trip_options([fare], request, ScoringContext())[0]
    wishlist = build_round_trip_options(
        [fare], request, ScoringContext(country_states={"US": "wishlist"})
    )[0]
    assert wishlist.dealScore == plain.dealScore
    assert wishlist.fitScore > plain.fitScore
    assert "Wishlist" in wishlist.tags


def test_indexed_aviasales_link_supports_return_and_open_jaw(monkeypatch):
    monkeypatch.setattr("app.providers.travelpayouts.affiliate_links.settings.travelpayouts_marker", "triplet")
    url = build_aviasales_itinerary_url(
        [
            ItinerarySegment("VIE", "JFK", "2026-10-01"),
            ItinerarySegment("NRT", "VIE", "2026-10-12"),
        ]
    )
    query = parse_qs(urlparse(url).query)
    assert query["segments[0][origin_iata]"] == ["VIE"]
    assert query["segments[0][destination_iata]"] == ["JFK"]
    assert query["segments[1][origin_iata]"] == ["NRT"]
    assert query["segments[1][destination_iata]"] == ["VIE"]
    assert query["marker"] == ["triplet"]


def test_global_open_jaw_builds_with_honest_self_transfer_and_itinerary_link(trip_data, monkeypatch):
    monkeypatch.setattr("app.providers.travelpayouts.affiliate_links.settings.travelpayouts_marker", "triplet")
    outbound_departure = datetime(2026, 10, 1, 9)
    return_departure = datetime(2026, 10, 12, 11)
    flights = [
        Flight(
            id="global-out", origin="VIE", destination="JFK",
            departureDateTime=outbound_departure, arrivalDateTime=outbound_departure + timedelta(hours=9),
            airline="OS", price=450, currency="EUR", provider="travelpayouts", stops=1,
        ),
        Flight(
            id="global-return", origin="NRT", destination="VIE",
            departureDateTime=return_departure, arrivalDateTime=return_departure + timedelta(hours=14),
            airline="OS", price=500, currency="EUR", provider="travelpayouts", stops=1,
        ),
    ]
    request = TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["JFK"], returnOriginAirports=["NRT"],
        startDate=date(2026, 10, 1), endDate=date(2026, 10, 5), minTripLengthDays=7,
        maxTripLengthDays=14, maxBudget=2000, maxGroundTransferHours=4, tripStyle="surprise me",
    )
    trips = build_trips(request, trip_data["airports"], flights, [], enforce_budget=False)
    assert len(trips) == 1
    trip = trips[0]
    assert trip.tripType == "open_jaw"
    assert trip.groundTransfer.mode == "ground/self-transfer"
    assert trip.destination.countryCode == "US"
    assert "segments%5B1%5D%5Borigin_iata%5D=NRT" in trip.bookingUrl
    assert any("not a protected flight connection" in warning for warning in trip.warnings)
