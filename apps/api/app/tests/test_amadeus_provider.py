import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.db.models import FlightDB
from app.providers.amadeus.auth import AmadeusAuthClient
from app.providers.amadeus.client import AmadeusConfigError
from app.providers.amadeus.mapper import map_amadeus_offer_to_flights, map_amadeus_offers
from app.providers.amadeus_flight_provider import AmadeusFlightProvider, generate_search_dates


def direct_offer():
    return {
        "id": "1",
        "validatingAirlineCodes": ["FR"],
        "itineraries": [
            {
                "segments": [
                    {
                        "carrierCode": "FR",
                        "departure": {"iataCode": "VIE", "at": "2026-07-12T07:15:00"},
                        "arrival": {"iataCode": "ALC", "at": "2026-07-12T10:05:00"},
                    }
                ]
            }
        ],
        "price": {"total": "39.99", "currency": "EUR"},
    }


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_amadeus_auth_missing_credentials_raises_clean_config_error():
    client = AmadeusAuthClient(client_id="", client_secret="")

    with pytest.raises(AmadeusConfigError, match="credentials are missing"):
        client.get_access_token()


def test_amadeus_auth_token_response_is_parsed(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse({"access_token": "token-1", "expires_in": 1800})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = AmadeusAuthClient(client_id="id", client_secret="secret")

    assert client.get_access_token() == "token-1"


def test_amadeus_auth_token_is_cached_until_expiry(monkeypatch):
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return FakeResponse({"access_token": "token-1", "expires_in": 1800})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = AmadeusAuthClient(client_id="id", client_secret="secret")

    assert client.get_access_token() == "token-1"
    assert client.get_access_token() == "token-1"
    assert calls["count"] == 1


def test_amadeus_mapper_maps_simple_direct_offer():
    flights = map_amadeus_offer_to_flights(direct_offer())

    assert len(flights) == 1
    assert flights[0].origin == "VIE"
    assert flights[0].destination == "ALC"
    assert flights[0].airline == "FR"
    assert flights[0].price == 39.99
    assert flights[0].provider == "amadeus"


def test_amadeus_mapper_skips_multi_itinerary_offer():
    offer = direct_offer()
    offer["itineraries"].append(offer["itineraries"][0])

    assert map_amadeus_offer_to_flights(offer) == []


def test_amadeus_mapper_fixture_maps_direct_offer():
    fixture_path = Path(__file__).parent / "fixtures" / "amadeus" / "direct_offer_response.json"
    payload = json.loads(fixture_path.read_text())

    result = map_amadeus_offers(payload)

    assert result.raw_offers_count == 1
    assert result.mapped_flights_count == 1
    assert result.flights[0].origin == "VIE"


def test_amadeus_mapper_malformed_offer_does_not_crash():
    result = map_amadeus_offers({"data": [{"id": "bad", "itineraries": [{"segments": []}]}]})

    assert result.flights == []
    assert result.skipped_offers_count == 1
    assert result.warnings


def test_generate_search_dates_samples_large_ranges():
    dates = generate_search_dates(date(2026, 7, 1), date(2026, 8, 31), max_dates=10)

    assert dates[0] == date(2026, 7, 1)
    assert len(dates) == 10


def test_amadeus_provider_uses_mocked_client_and_caches(db_session):
    class FakeClient:
        def get(self, path, params):
            return {"data": [direct_offer()]}

    provider = AmadeusFlightProvider(db=db_session, client=FakeClient(), max_requests=1, cache_enabled=True)
    flights = provider.search_flights(["VIE"], date(2026, 7, 12), date(2026, 7, 12), ["ALC"])

    assert flights
    cached = list(db_session.execute(select(FlightDB)).scalars())
    assert any(row.provider == "amadeus" for row in cached)
