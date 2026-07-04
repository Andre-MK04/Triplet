from datetime import date

import httpx
import pytest

from app.providers.flight_provider import DateRange
from app.providers.travelpayouts.client import (
    TravelpayoutsAuthError,
    TravelpayoutsConfigError,
    TravelpayoutsHttpClient,
)
from app.providers.travelpayouts.flight_provider import (
    TravelpayoutsAviasalesProvider,
    months_in_range,
)
from app.providers.travelpayouts.mapper import map_prices_for_dates_response_to_flights


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def prices_payload():
    return {
        "success": True,
        "currency": "eur",
        "data": [
            {
                "origin": "VIE",
                "destination": "ALC",
                "departure_at": "2026-08-15T07:05:00+02:00",
                "price": 64,
                "airline": "FR",
                "flight_number": "1234",
                "transfers": 0,
                "duration_to": 175,
                "link": "/search/VIE1508ALC1?t=abc",
            },
            {
                # No duration: we cannot state an honest arrival time, so it must be skipped.
                "origin": "VIE",
                "destination": "ALC",
                "departure_at": "2026-08-16T07:05:00+02:00",
                "price": 70,
                "airline": "W6",
                "transfers": 1,
                "link": "/search/VIE1608ALC1",
            },
        ],
    }


def test_travelpayouts_client_sends_access_token_header(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse(prices_payload())

    monkeypatch.setattr(httpx, "get", fake_get)
    client = TravelpayoutsHttpClient(api_token="tp-secret")

    client.prices_for_dates("vie", "alc", "2026-08")

    assert captured["headers"]["X-Access-Token"] == "tp-secret"
    assert captured["params"]["origin"] == "VIE"
    assert "/aviasales/v3/prices_for_dates" in captured["url"]


def test_travelpayouts_client_raises_without_token():
    with pytest.raises(TravelpayoutsConfigError):
        TravelpayoutsHttpClient(api_token="").prices_for_dates("VIE", "ALC", "2026-08")


def test_travelpayouts_client_handles_auth_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: FakeResponse({}, status_code=403))
    with pytest.raises(TravelpayoutsAuthError):
        TravelpayoutsHttpClient(api_token="token").prices_for_dates("VIE", "ALC", "2026-08")


def test_travelpayouts_mapper_marks_fares_indicative_and_builds_affiliate_link():
    result = map_prices_for_dates_response_to_flights(prices_payload(), marker="triplet-marker")

    assert result.raw_offers_count == 2
    assert result.mapped_flights_count == 1
    assert result.skipped_offers_count == 1
    flight = result.flights[0]
    assert flight.provider == "travelpayouts"
    assert flight.confidenceLevel == "indicative"
    assert flight.isLive is False
    assert flight.price == 64
    assert flight.currency == "EUR"
    assert flight.stops == 0
    assert flight.deepLink.startswith("https://www.aviasales.com/search/VIE1508ALC1")
    assert "marker=triplet-marker" in flight.affiliateUrl


def test_travelpayouts_mapper_without_marker_has_no_affiliate_url():
    result = map_prices_for_dates_response_to_flights(prices_payload(), marker=None)

    flight = result.flights[0]
    assert flight.deepLink
    assert flight.affiliateUrl is None
    assert "marker=" not in flight.deepLink


def test_months_in_range_spans_months():
    months = months_in_range(DateRange(start=date(2026, 7, 20), end=date(2026, 9, 3)))

    assert months == ["2026-07", "2026-08", "2026-09"]


def test_travelpayouts_provider_disabled_returns_no_flights_with_warning(monkeypatch):
    monkeypatch.setattr(
        "app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_enabled", False
    )
    provider = TravelpayoutsAviasalesProvider()

    flights = provider.search_one_way("VIE", "ALC", date(2026, 8, 15))

    assert flights == []
    assert any("disabled" in warning.lower() for warning in provider.warnings)


def test_travelpayouts_provider_filters_results_to_requested_dates(db_session, monkeypatch):
    class FakeClient:
        def prices_for_dates(self, origin, destination, month, **kwargs):
            return prices_payload()

    monkeypatch.setattr(
        "app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_enabled", True
    )
    provider = TravelpayoutsAviasalesProvider(db=db_session, client=FakeClient(), cache_enabled=False)

    flights = provider.search_flexible(["VIE"], ["ALC"], DateRange(start=date(2026, 8, 1), end=date(2026, 8, 31)))

    assert flights
    assert all(date(2026, 8, 1) <= f.departureDateTime.date() <= date(2026, 8, 31) for f in flights)


def test_travelpayouts_status_not_configured_without_token(monkeypatch):
    monkeypatch.setattr(
        "app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_token", None
    )
    monkeypatch.setattr(
        "app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_enabled", False
    )

    status = TravelpayoutsAviasalesProvider().get_provider_status()

    assert status.name == "travelpayouts"
    assert status.accessStatus == "not_configured"
    assert status.capabilities.liveAvailability is False
    assert status.capabilities.affiliateLinks is True
    assert "TRAVELPAYOUTS_API_TOKEN" in status.requiredEnvVars
