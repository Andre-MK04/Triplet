from datetime import date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Flight
from app.providers import caching
from app.providers.caching import cache_flights
from app.providers.travelpayouts.flight_provider import TravelpayoutsAviasalesProvider
from app.providers.flight_provider import DateRange


def a_flight(destination: str = "STO") -> Flight:
    # STO is a metro code not in the seeded airports table — the real prod case.
    return Flight(
        id=f"tp-{destination}",
        origin="VIE",
        destination=destination,
        departureDateTime=datetime(2026, 8, 5, 9, 0),
        arrivalDateTime=datetime(2026, 8, 5, 12, 0),
        airline="LW",
        price=62.0,
        provider="travelpayouts",
        confidenceLevel="indicative",
    )


def test_cache_flights_swallows_db_errors(db_session, monkeypatch):
    def boom(self, flights):
        raise IntegrityError("insert", {}, Exception("FK violation"))

    monkeypatch.setattr(
        "app.db.repositories.flights_repository.FlightsRepository.upsert_flights", boom
    )

    # Must not raise, and must report zero cached rather than propagating.
    assert cache_flights(db_session, [a_flight()]) == 0


def test_search_returns_flights_even_when_caching_fails(db_session, monkeypatch):
    class FakeClient:
        def prices_for_dates(self, origin, destination, month, **kwargs):
            return {
                "success": True,
                "currency": "eur",
                "data": [
                    {
                        "origin": "VIE",
                        "destination": "STO",
                        "departure_at": "2026-08-05T09:00:00+02:00",
                        "price": 62,
                        "airline": "LW",
                        "transfers": 0,
                        "duration_to": 180,
                        "link": "/search/VIE0508STO1",
                    }
                ],
            }

    # Simulate the production FK violation on cache write.
    def boom(self, flights):
        raise IntegrityError("insert", {}, Exception("FK violation on STO"))

    monkeypatch.setattr("app.providers.travelpayouts.flight_provider.settings.travelpayouts_api_enabled", True)
    monkeypatch.setattr(
        "app.db.repositories.flights_repository.FlightsRepository.upsert_flights", boom
    )
    provider = TravelpayoutsAviasalesProvider(db=db_session, client=FakeClient(), cache_enabled=True)

    flights = provider.search_flexible(["VIE"], ["STO"], DateRange(start=date(2026, 8, 1), end=date(2026, 8, 31)))

    # The search still yields the fare; caching just silently failed.
    assert any(f.destination == "STO" for f in flights)
    assert provider.cached_flights_count == 0
