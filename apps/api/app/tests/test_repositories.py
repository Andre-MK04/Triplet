from datetime import date

from app.db.models import AirportAreaDB, AirportDB, FlightDB, GroundTransferDB
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.flights_repository import FlightsRepository
from app.db.repositories.transfers_repository import TransfersRepository


def test_seed_data_can_be_inserted(db_session):
    assert db_session.query(AirportAreaDB).count() >= 18
    assert db_session.query(AirportDB).count() >= 19
    assert db_session.query(FlightDB).count() >= 50
    assert db_session.query(GroundTransferDB).count() == 12


def test_airports_can_be_listed(db_session):
    airports = AirportsRepository(db_session).list_airports()

    assert len(airports) >= 19
    assert any(airport.code == "VIE" and airport.areaSlug == "vienna" for airport in airports)
    # Nordic destinations are seeded so "trip to Scandinavia" has somewhere to go.
    assert {"CPH", "OSL", "ARN", "HEL"} <= {airport.code for airport in airports}


def test_origin_candidate_airports_can_be_listed(db_session):
    airports = AirportsRepository(db_session).list_origin_candidates()

    assert {airport.code for airport in airports} == {"LJU", "ZAG", "VIE", "GRZ", "BUD", "TRS", "VCE", "TSF"}


def test_flights_can_be_loaded_from_database(db_session):
    flights = FlightsRepository(db_session).list_all_mock_flights()

    assert len(flights) >= 50
    assert any(flight.origin == "VIE" and flight.destination == "ALC" for flight in flights)


def test_ground_transfers_can_be_loaded_from_database(db_session):
    transfers = TransfersRepository(db_session).list_transfers()

    assert len(transfers) == 12
    assert any(transfer.fromAirport == "ALC" and transfer.toAirport == "VLC" for transfer in transfers)


def test_transfer_repository_can_find_area_match(db_session):
    transfer = TransfersRepository(db_session).find_transfer_between_areas_or_airports("TSF", "TRS")

    assert transfer is not None
    assert transfer.fromAirport == "VCE"
    assert transfer.toAirport == "TRS"


def test_upsert_flights_stores_new_flights(db_session):
    repository = FlightsRepository(db_session)
    flight = repository.list_all_mock_flights()[0].model_copy(update={"id": "cache-test-1", "provider": "skyscanner"})

    repository.upsert_flights([flight])

    assert db_session.get(FlightDB, "cache-test-1").provider == "skyscanner"


def test_upsert_flights_updates_existing_flights_without_duplication(db_session):
    repository = FlightsRepository(db_session)
    flight = repository.list_all_mock_flights()[0].model_copy(update={"id": "cache-test-2", "price": 100, "provider": "skyscanner"})
    repository.upsert_flights([flight])
    repository.upsert_flights([flight.model_copy(update={"price": 80})])

    rows = db_session.query(FlightDB).filter(FlightDB.id == "cache-test-2").all()
    assert len(rows) == 1
    assert rows[0].price == 80


def test_cached_flights_can_be_loaded(db_session):
    flights = FlightsRepository(db_session).get_cached_flights(["VIE"], date(2026, 7, 1), date(2026, 8, 31))

    assert flights
