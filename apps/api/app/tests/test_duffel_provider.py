from datetime import date

import httpx
import pytest

from app.providers.duffel.client import DuffelAuthError, DuffelConfigError, DuffelHttpClient, DuffelRateLimitError
from app.providers.duffel.flight_provider import (
    DuffelFlightProvider,
    build_one_way_offer_request_payload,
)
from app.providers.duffel.mapper import map_offer_request_response_to_flights


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def offer_request_payload():
    return {
        "data": {
            "id": "orq_0000A",
            "offers": [
                {
                    "id": "off_0000B",
                    "total_amount": "89.40",
                    "total_currency": "EUR",
                    "expires_at": "2026-08-15T12:00:00Z",
                    "owner": {"name": "Austrian Airlines", "iata_code": "OS"},
                    "slices": [
                        {
                            "segments": [
                                {
                                    "origin": {"iata_code": "VIE"},
                                    "destination": {"iata_code": "ALC"},
                                    "departing_at": "2026-08-15T07:10:00",
                                    "arriving_at": "2026-08-15T10:05:00",
                                    "marketing_carrier": {"name": "Austrian Airlines", "iata_code": "OS"},
                                    "passengers": [
                                        {"baggages": [{"type": "checked", "quantity": 1}]}
                                    ],
                                }
                            ]
                        }
                    ],
                },
                {"id": "off_bad", "slices": []},
            ],
        }
    }


def test_duffel_client_sends_bearer_token_and_version(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResponse({"data": {"offers": []}})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = DuffelHttpClient(api_key="duffel_test_secret")

    client.create_offer_request({"data": {}})

    assert captured["headers"]["Authorization"] == "Bearer duffel_test_secret"
    assert captured["headers"]["Duffel-Version"]
    assert "/air/offer_requests" in captured["url"]


def test_duffel_client_raises_without_api_key():
    with pytest.raises(DuffelConfigError):
        DuffelHttpClient(api_key="").create_offer_request({})


def test_duffel_client_handles_auth_and_rate_limit(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse({}, status_code=401))
    with pytest.raises(DuffelAuthError):
        DuffelHttpClient(api_key="key").create_offer_request({})

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse({}, status_code=429))
    with pytest.raises(DuffelRateLimitError):
        DuffelHttpClient(api_key="key").create_offer_request({})


def test_duffel_mapper_maps_offer_with_baggage_and_expiry():
    result = map_offer_request_response_to_flights(offer_request_payload())

    assert result.raw_offers_count == 2
    assert result.mapped_flights_count == 1
    assert result.skipped_offers_count == 1
    flight = result.flights[0]
    assert flight.origin == "VIE"
    assert flight.destination == "ALC"
    assert flight.price == 89.40
    assert flight.provider == "duffel"
    assert flight.confidenceLevel == "live"
    assert flight.isLive is True
    assert flight.baggageIncluded is True
    assert flight.expiresAt is not None
    assert flight.observedAt is not None
    assert flight.deepLink is None  # Duffel is a booking API; no public deep link.


def test_duffel_payload_contains_slice_and_cabin():
    payload = build_one_way_offer_request_payload("vie", "alc", date(2026, 8, 15), passengers=2, cabin="business")

    data = payload["data"]
    assert data["slices"][0] == {"origin": "VIE", "destination": "ALC", "departure_date": "2026-08-15"}
    assert len(data["passengers"]) == 2
    assert data["cabin_class"] == "business"


def test_duffel_provider_disabled_returns_no_flights_with_warning(monkeypatch):
    monkeypatch.setattr("app.providers.duffel.flight_provider.settings.duffel_api_enabled", False)
    provider = DuffelFlightProvider()

    flights = provider.search_one_way("VIE", "ALC", date(2026, 8, 15))

    assert flights == []
    assert any("disabled" in warning.lower() for warning in provider.warnings)


def test_duffel_provider_searches_and_caches_with_fake_client(db_session, monkeypatch):
    class FakeClient:
        def create_offer_request(self, payload):
            return offer_request_payload()

    monkeypatch.setattr("app.providers.duffel.flight_provider.settings.duffel_api_enabled", True)
    provider = DuffelFlightProvider(db=db_session, client=FakeClient(), max_requests=1, cache_enabled=True)

    flights = provider.search_one_way("VIE", "ALC", date(2026, 8, 15))

    assert flights
    assert provider.requests_attempted == 1
    assert provider.mapped_flights_count == 1
    assert provider.cached_flights_count == 1


def test_duffel_status_not_configured_without_key(monkeypatch):
    monkeypatch.setattr("app.providers.duffel.flight_provider.settings.duffel_api_key", None)
    monkeypatch.setattr("app.providers.duffel.flight_provider.settings.duffel_api_enabled", False)

    status = DuffelFlightProvider().get_provider_status()

    assert status.name == "duffel"
    assert status.accessStatus == "not_configured"
    assert status.configured is False
    assert status.capabilities.liveAvailability is True
    assert status.capabilities.deepLinks is False
    assert "DUFFEL_API_KEY" in status.requiredEnvVars


def test_duffel_smoke_test_skips_cleanly_without_credentials(monkeypatch):
    monkeypatch.setattr("app.providers.duffel.flight_provider.settings.duffel_api_key", None)
    monkeypatch.setattr("app.providers.duffel.flight_provider.settings.duffel_api_enabled", False)

    result = DuffelFlightProvider().smoke_test()

    assert result.provider == "duffel"
    assert result.ok is False
    assert result.apiOk is False
    assert result.warnings
