from datetime import date

import pytest

from app.db.repositories.flights_repository import FlightsRepository
from app.providers.database_flight_provider import DatabaseFlightProvider
from app.providers.mock_flight_provider import MockFlightProvider
from app.providers.errors import ProviderApiError
from app.models import ProviderMetadata, TripSearchRequest
from app.providers.travelpayouts.mapper import OneWayFare
from app.services.flight_search_service import (
    FlightSearchService,
    UnknownFlightProviderError,
)


def test_database_flight_provider_returns_normalized_flights(db_session):
    provider = DatabaseFlightProvider(db_session)

    flights = provider.search_outbound_flights(["VIE"], date(2026, 7, 1), date(2026, 7, 31))

    assert flights
    assert all(flight.origin == "VIE" for flight in flights)
    assert all(hasattr(flight, "departureDateTime") for flight in flights)


def test_database_flight_provider_filters_by_origin_codes(db_session):
    provider = DatabaseFlightProvider(db_session)

    flights = provider.search_flights(["ZAG"], date(2026, 7, 1), date(2026, 8, 31))

    assert flights
    assert {flight.origin for flight in flights} == {"ZAG"}


def test_database_flight_provider_filters_by_date_range(db_session):
    provider = DatabaseFlightProvider(db_session)

    flights = provider.search_flights(["VIE"], date(2026, 7, 12), date(2026, 7, 12))

    assert flights
    assert all(flight.departureDateTime.date() == date(2026, 7, 12) for flight in flights)


def test_database_flight_provider_filters_by_destination_codes(db_session):
    provider = DatabaseFlightProvider(db_session)

    flights = provider.search_flights(["VIE"], date(2026, 7, 1), date(2026, 8, 31), ["ALC"])

    assert flights
    assert {flight.destination for flight in flights} == {"ALC"}


def test_mock_flight_provider_filters_expected_flights(db_session):
    flights = FlightsRepository(db_session).list_all_mock_flights()
    provider = MockFlightProvider(flights)

    results = provider.search_flights(["VIE"], date(2026, 7, 1), date(2026, 7, 31), ["ALC"])

    assert [flight.id for flight in results] == ["f001"]


def test_flight_search_service_uses_database_provider_by_default(db_session):
    service = FlightSearchService(db=db_session, provider_name="database")

    results = service.search_flights(["VIE"], date(2026, 7, 1), date(2026, 8, 31))

    assert results


def test_flight_search_service_rejects_unknown_provider(db_session):
    with pytest.raises(UnknownFlightProviderError, match="Unknown flight provider"):
        FlightSearchService(db=db_session, provider_name="unknown")


def test_flight_search_service_recognizes_skyscanner_provider(db_session):
    service = FlightSearchService(db=db_session, provider_name="skyscanner")

    assert service.provider_name == "skyscanner"


def test_hybrid_mode_falls_back_to_database_when_live_provider_fails(db_session, monkeypatch):
    class FailingLiveProvider(MockFlightProvider):
        name = "failing-live"

        def search_flexible(self, *args, **kwargs):
            raise ProviderApiError("mock live provider failure")

    monkeypatch.setattr(
        "app.services.flight_search_service.build_live_provider",
        lambda db=None: FailingLiveProvider([]),
    )
    service = FlightSearchService(db=db_session, provider_name="hybrid")
    request = TripSearchRequest(
        originAirports=["VIE", "ZAG"],
        startDate=date(2026, 7, 1),
        endDate=date(2026, 8, 31),
        minTripLengthDays=4,
        maxTripLengthDays=8,
        maxBudget=180,
        maxGroundTransferHours=4,
        tripStyle="surprise me",
    )

    result = service.search_candidate_flights_with_metadata(request)

    assert result.flights
    assert result.metadata.providerUsed == "database"
    assert result.metadata.cachedResultsUsed is True
    assert result.metadata.providerWarnings


def test_a_thin_later_origin_does_not_erase_an_earlier_provider_success():
    class SequentialLegProvider:
        name = "travelpayouts"
        warnings: list[str] = []
        requests_attempted = 1

        def __init__(self):
            self.calls = 0

        def one_way_legs(self, legs, _window):
            self.calls += 1
            if self.calls == 1:
                origin, destination = legs[0]
                return {
                    (origin, destination): [
                        OneWayFare(
                            origin=origin,
                            destination=destination,
                            departureDate="2026-10-10",
                            price=120,
                        )
                    ]
                }
            return {leg: [] for leg in legs}

    request = TripSearchRequest(
        originAirports=["CPH", "MMA"],
        startDate=date(2026, 9, 1),
        endDate=date(2026, 12, 29),
        minTripLengthDays=14,
        maxTripLengthDays=21,
        maxBudget=1500,
        maxGroundTransferHours=4,
        tripStyle="surprise me",
        tripPlan="multi_city",
        routeStops=["TYO", "SEL", "SHA"],
    )
    service = FlightSearchService(
        provider_name="travelpayouts",
        provider=SequentialLegProvider(),
    )

    service.one_way_fares_for(request, [("CPH", "TYO")])
    service.one_way_fares_for(request, [("MMA", "TYO")])
    metadata = service.apply_deal_metadata(ProviderMetadata())

    assert metadata.liveProviderSucceeded is True
