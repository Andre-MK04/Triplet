from datetime import date, datetime

from app.db.repositories.flights_repository import FlightsRepository
from app.db.repositories.price_observations_repository import PriceObservationsRepository
from app.models import Flight
from app.providers.flight_provider import DateRange
from app.providers.mock_flight_provider import MockFlightProvider
from app.providers.registry import all_provider_statuses, build_provider


def make_flight(**overrides) -> Flight:
    base = dict(
        id="t-1",
        origin="VIE",
        destination="ALC",
        departureDateTime=datetime(2026, 8, 15, 7, 0),
        arrivalDateTime=datetime(2026, 8, 15, 10, 0),
        airline="Test Air",
        price=79.0,
        currency="EUR",
        provider="duffel",
        confidenceLevel="live",
        deepLink="https://example.com/deal",
    )
    base.update(overrides)
    return Flight(**base)


def test_mock_provider_search_one_way_and_return():
    outbound = make_flight()
    inbound = make_flight(
        id="t-2",
        origin="ALC",
        destination="VIE",
        departureDateTime=datetime(2026, 8, 20, 11, 0),
        arrivalDateTime=datetime(2026, 8, 20, 14, 0),
    )
    provider = MockFlightProvider([outbound, inbound])

    one_way = provider.search_one_way("VIE", "ALC", date(2026, 8, 15))
    both = provider.search_return("VIE", "ALC", date(2026, 8, 15), date(2026, 8, 20))

    assert [flight.id for flight in one_way] == ["t-1"]
    assert {flight.id for flight in both} == {"t-1", "t-2"}


def test_mock_provider_search_flexible_with_open_scope():
    provider = MockFlightProvider([make_flight()])

    anywhere = provider.search_flexible(["VIE"], None, DateRange(start=date(2026, 8, 1), end=date(2026, 8, 31)))
    wrong_dates = provider.search_flexible(["VIE"], None, DateRange(start=date(2026, 9, 1), end=date(2026, 9, 30)))

    assert len(anywhere) == 1
    assert wrong_dates == []


def test_mock_provider_smoke_test_reports_honestly():
    provider = MockFlightProvider([make_flight(departureDateTime=datetime(2026, 8, 18, 7, 0))])

    result = provider.smoke_test(origin="VIE", destination="ALC", departure_date=date(2026, 8, 18))

    assert result.ok is True
    assert result.apiOk is True
    assert result.sampleFlight["confidenceLevel"] == "live"
    assert "price" in result.sampleFlight


def test_all_provider_statuses_cover_registry(db_session):
    statuses = all_provider_statuses(db_session)
    names = {status.name for status in statuses}

    assert {"mock", "database", "duffel", "travelpayouts", "skyscanner"} <= names
    for status in statuses:
        assert status.accessStatus in {"available", "requires_approval", "not_configured", "disabled"}
        assert status.implementationStatus in {"implemented", "adapter_only", "planned"}


def test_skyscanner_status_requires_approval_without_key(monkeypatch, db_session):
    monkeypatch.setattr("app.config.settings.skyscanner_api_key", None)

    status = build_provider("skyscanner", db_session).get_provider_status()

    assert status.accessStatus == "requires_approval"


def test_database_provider_reads_back_cached_confidence(db_session):
    repository = FlightsRepository(db_session)
    repository.upsert_flights([make_flight(observedAt=datetime(2026, 7, 1, 12, 0))])

    provider = build_provider("database", db_session)
    flights = provider.search_one_way("VIE", "ALC", date(2026, 8, 15))

    assert flights
    flight = flights[0]
    assert flight.confidenceLevel == "cached"
    assert flight.isLive is False
    assert flight.observedAt is not None


def test_price_observations_recorded_and_deduplicated(db_session):
    repository = PriceObservationsRepository(db_session)
    flight = make_flight()

    first = repository.record_flights([flight])
    second = repository.record_flights([flight])

    assert first == 1
    assert second == 0  # identical observation within the duplicate window

    stats = repository.route_stats("VIE", "ALC")
    assert stats["count"] == 1
    assert stats["minPrice"] == 79.0


def test_price_observations_ignore_mock_and_cached_fares(db_session):
    repository = PriceObservationsRepository(db_session)

    recorded = repository.record_flights(
        [
            make_flight(id="m-1", provider="mock", confidenceLevel="mock"),
            make_flight(id="c-1", provider="database", confidenceLevel="cached"),
        ]
    )

    assert recorded == 0


def test_price_observations_record_indicative_fares(db_session):
    repository = PriceObservationsRepository(db_session)

    recorded = repository.record_flights(
        [make_flight(id="i-1", provider="travelpayouts", confidenceLevel="indicative", price=45.0)]
    )

    assert recorded == 1
    observations = repository.observations_for_route("VIE", "ALC")
    assert observations[0].confidence == "indicative"
    assert observations[0].link_available is True
