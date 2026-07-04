from datetime import date

import httpx
import pytest
from sqlalchemy import select

from app.db.models import FlightDB
from app.providers.skyscanner.affiliate_links import SkyscannerAffiliateLinkBuilder
from app.providers.skyscanner.client import (
    SkyscannerAuthError,
    SkyscannerHttpClient,
    SkyscannerRateLimitError,
)
from app.providers.skyscanner.flight_provider import (
    SkyscannerFlightProvider,
    build_one_way_live_search_payload,
    generate_search_dates,
)
from app.providers.skyscanner.mapper import map_live_response_to_flights


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def live_payload():
    return {
        "content": {
            "itineraries": [
                {
                    "id": "itin-1",
                    "legIds": ["leg-1"],
                    "pricingOptions": [
                        {"price": {"amount": 55.5}, "deepLink": "https://skyscanner.example/deep", "agentIds": ["agent-1"]},
                        {"price": {"amount": 75}, "deepLink": "https://skyscanner.example/expensive"},
                    ],
                }
            ],
            "legs": {
                "leg-1": {
                    "id": "leg-1",
                    "segmentIds": ["seg-1", "seg-2"],
                    "durationInMinutes": 220,
                }
            },
            "segments": {
                "seg-1": {
                    "id": "seg-1",
                    "originPlaceId": "place-vie",
                    "destinationPlaceId": "place-fco",
                    "departureDateTime": "2026-08-15T07:00:00",
                    "arrivalDateTime": "2026-08-15T08:30:00",
                    "marketingCarrierId": "carrier-os",
                },
                "seg-2": {
                    "id": "seg-2",
                    "originPlaceId": "place-fco",
                    "destinationPlaceId": "place-alc",
                    "departureDateTime": "2026-08-15T09:20:00",
                    "arrivalDateTime": "2026-08-15T11:40:00",
                    "marketingCarrierId": "carrier-os",
                },
            },
            "places": {
                "place-vie": {"iata": "VIE"},
                "place-fco": {"iata": "FCO"},
                "place-alc": {"iata": "ALC"},
            },
            "carriers": {"carrier-os": {"name": "Austrian"}},
            "agents": {"agent-1": {"name": "Skyscanner partner"}},
        }
    }


def test_skyscanner_client_sends_x_api_key_header(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return FakeResponse({"sessionToken": "token-1"})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = SkyscannerHttpClient(api_key="secret-key")

    client.create_live_price_search({"query": {}})

    assert captured["headers"]["x-api-key"] == "secret-key"


def test_skyscanner_client_handles_auth_and_rate_limit(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse({}, status_code=403))
    with pytest.raises(SkyscannerAuthError):
        SkyscannerHttpClient(api_key="secret-key").create_live_price_search({})

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse({}, status_code=429))
    with pytest.raises(SkyscannerRateLimitError):
        SkyscannerHttpClient(api_key="secret-key").create_live_price_search({})


def test_live_price_polling_uses_session_token_and_stops(monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append(url)
        if url.endswith("/create"):
            return FakeResponse({"sessionToken": "abc"})
        return FakeResponse({"status": "COMPLETED", **live_payload()})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = SkyscannerHttpClient(api_key="secret-key", poll_attempts=3, poll_delay_seconds=0)
    response = client.run_live_price_search({"query": {}})

    assert "poll/abc" in calls[1]
    assert response["status"] == "COMPLETED"
    assert len(calls) == 2


def test_build_one_way_live_search_payload_contains_market_locale_currency():
    payload = build_one_way_live_search_payload("VIE", "ALC", date(2026, 8, 15))

    query = payload["query"]
    assert query["market"] == "SI"
    assert query["locale"] == "en-GB"
    assert query["currency"] == "EUR"
    assert query["queryLegs"][0]["originPlaceId"]["iata"] == "VIE"


def test_skyscanner_mapper_maps_connection_and_deep_link():
    result = map_live_response_to_flights(live_payload())

    assert result.mapped_flights_count == 1
    flight = result.flights[0]
    assert flight.origin == "VIE"
    assert flight.destination == "ALC"
    assert flight.price == 55.5
    assert flight.bookingUrl == "https://skyscanner.example/deep"
    assert flight.agentName == "Skyscanner partner"
    assert flight.stops == 1


def test_skyscanner_mapper_malformed_itinerary_does_not_crash():
    result = map_live_response_to_flights({"content": {"itineraries": [{"id": "bad"}]}})

    assert result.flights == []
    assert result.skipped_offers_count == 1
    assert result.warnings


def test_skyscanner_affiliate_builder_generates_tracked_day_view_link():
    builder = SkyscannerAffiliateLinkBuilder(enabled=True, media_partner_id="partner-1")
    link = builder.build_day_view_link("VIE", "ALC", date(2026, 8, 15), utm_term="test")

    assert link
    assert "mediaPartnerId=partner-1" in link
    assert "utm_source=triplet" in link
    assert "day-view" in link


def test_skyscanner_affiliate_builder_returns_none_when_unconfigured():
    builder = SkyscannerAffiliateLinkBuilder(enabled=True, media_partner_id="")

    assert builder.build_browse_view_link("VIE", "ALC") is None


def test_skyscanner_provider_uses_mocked_client_and_caches(db_session, monkeypatch):
    class FakeClient:
        def run_live_price_search(self, payload):
            return live_payload()

    monkeypatch.setattr("app.providers.skyscanner.flight_provider.settings.skyscanner_api_enabled", True)
    provider = SkyscannerFlightProvider(db=db_session, client=FakeClient(), max_requests=1, cache_enabled=True)
    flights = provider.search_flights(["VIE"], date(2026, 8, 15), date(2026, 8, 15), ["ALC"])

    assert flights
    cached = list(db_session.execute(select(FlightDB)).scalars())
    assert any(row.provider == "skyscanner" and row.deep_link for row in cached)
