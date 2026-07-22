from fastapi.testclient import TestClient

from app.database import get_db
from app.db.models import AirportDirectoryDB, LocationDB
from app.main import app


def make_client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def seed_geo(db):
    db.add_all(
        [
            LocationDB(id=1, name="Ljubljana", ascii_name="Ljubljana", country_code="SI",
                       country_name="Slovenia", latitude=46.05, longitude=14.51, population=280000),
            LocationDB(id=2, name="Ljutomer", ascii_name="Ljutomer", country_code="SI",
                       country_name="Slovenia", latitude=46.52, longitude=16.19, population=3300),
            LocationDB(id=3, name="Paris", ascii_name="Paris", country_code="FR",
                       country_name="France", latitude=48.86, longitude=2.35, population=2100000),
            LocationDB(id=4, name="Maribor", ascii_name="Maribor", country_code="SI",
                       country_name="Slovenia", latitude=46.55, longitude=15.65, population=95000),
        ]
    )
    db.add_all(
        [
            AirportDirectoryDB(id=10, iata_code="LJU", name="Ljubljana Jože Pučnik Airport", city="Ljubljana",
                               country_code="SI", country_name="Slovenia", latitude=46.22, longitude=14.46,
                               type="medium_airport", scheduled_service=True, is_active=True),
            AirportDirectoryDB(id=11, iata_code="VIE", name="Vienna International Airport", city="Vienna",
                               country_code="AT", country_name="Austria", latitude=48.11, longitude=16.57,
                               type="large_airport", scheduled_service=True, is_active=True),
            AirportDirectoryDB(id=12, iata_code="CDG", name="Charles de Gaulle International Airport", city="Paris",
                               country_code="FR", country_name="France", latitude=49.01, longitude=2.55,
                               type="large_airport", scheduled_service=True, is_active=True),
            AirportDirectoryDB(id=13, iata_code="ORY", name="Paris-Orly Airport", city="Paris",
                               country_code="FR", country_name="France", latitude=48.72, longitude=2.38,
                               type="large_airport", scheduled_service=True, is_active=True),
            AirportDirectoryDB(id=14, iata_code="TRS", name="Trieste – Friuli Venezia Giulia Airport", city="Trieste",
                               country_code="IT", country_name="Italy", latitude=45.83, longitude=13.47,
                               type="medium_airport", scheduled_service=True, is_active=True),
            # Should never surface: inactive and unscheduled fields.
            AirportDirectoryDB(id=15, iata_code="XXA", name="Closed Field", city="Nowhere",
                               country_code="SI", country_name="Slovenia", latitude=46.2, longitude=14.6,
                               type="closed", scheduled_service=False, is_active=False),
            AirportDirectoryDB(id=16, iata_code="XXB", name="Private Strip", city="Ljubljana",
                               country_code="SI", country_name="Slovenia", latitude=46.1, longitude=14.5,
                               type="small_airport", scheduled_service=False, is_active=True),
        ]
    )
    db.commit()


def test_location_search_matches_towns_and_orders_by_population(db_session):
    seed_geo(db_session)
    client = make_client(db_session)

    res = client.get("/locations/search", params={"q": "lju"})
    app.dependency_overrides.clear()

    assert res.status_code == 200
    names = [row["name"] for row in res.json()]
    assert names[0] == "Ljubljana"  # bigger city first
    assert "Ljutomer" in names
    first = res.json()[0]
    assert first["countryName"] == "Slovenia"
    assert round(first["latitude"]) == 46


def test_location_search_no_results_is_empty_list(db_session):
    seed_geo(db_session)
    client = make_client(db_session)
    res = client.get("/locations/search", params={"q": "zzzz"})
    app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == []


def test_airport_search_by_city_name_and_iata(db_session):
    seed_geo(db_session)
    client = make_client(db_session)

    by_city = client.get("/airports/search", params={"q": "paris"}).json()
    by_iata = client.get("/airports/search", params={"q": "vie"}).json()
    by_name = client.get("/airports/search", params={"q": "pučnik"}).json()
    app.dependency_overrides.clear()

    assert {a["iataCode"] for a in by_city} == {"CDG", "ORY"}
    assert by_iata[0]["iataCode"] == "VIE"  # exact IATA match ranks first
    assert by_name and by_name[0]["iataCode"] == "LJU"


def test_airport_search_excludes_inactive_and_unscheduled(db_session):
    seed_geo(db_session)
    client = make_client(db_session)
    res = client.get("/airports/search", params={"q": "ljubljana"}).json()
    app.dependency_overrides.clear()
    codes = {a["iataCode"] for a in res}
    assert "LJU" in codes
    assert "XXA" not in codes and "XXB" not in codes


def test_recommended_airports_by_location_sorted_by_distance(db_session):
    seed_geo(db_session)
    client = make_client(db_session)

    res = client.get("/airports/recommended", params={"locationId": 1, "maxDistanceKm": 300})
    app.dependency_overrides.clear()

    assert res.status_code == 200
    rows = res.json()
    codes = [row["iataCode"] for row in rows]
    assert codes[0] == "LJU"  # nearest to Ljubljana
    assert "TRS" in codes and "VIE" in codes  # both within 300 km
    assert "CDG" not in codes  # Paris is far away
    assert rows[0]["distanceKm"] < rows[-1]["distanceKm"] + 100  # distances present
    assert all(row["distanceKm"] is not None for row in rows)


def test_recommended_airports_respects_distance_cap(db_session):
    seed_geo(db_session)
    client = make_client(db_session)
    res = client.get("/airports/recommended", params={"locationId": 1, "maxDistanceKm": 60}).json()
    app.dependency_overrides.clear()
    codes = [row["iataCode"] for row in res]
    assert codes == ["LJU"]


def test_get_airport_by_iata(db_session):
    seed_geo(db_session)
    client = make_client(db_session)
    res = client.get("/airports/LJU")
    missing = client.get("/airports/ZZZ")
    app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json()["name"].startswith("Ljubljana")
    assert missing.status_code == 404
