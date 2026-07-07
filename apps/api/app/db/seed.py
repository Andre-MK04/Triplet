from datetime import datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.db.models import AirportAreaDB, AirportDB, FlightDB, GroundTransferDB


AIRPORT_AREAS = [
    ("ljubljana", "Ljubljana", "Slovenia"),
    ("zagreb", "Zagreb", "Croatia"),
    ("vienna", "Vienna", "Austria"),
    ("graz", "Graz", "Austria"),
    ("budapest", "Budapest", "Hungary"),
    ("trieste", "Trieste", "Italy"),
    ("venice", "Venice", "Italy"),
    ("alicante", "Alicante", "Spain"),
    ("valencia", "Valencia", "Spain"),
    ("barcelona", "Barcelona", "Spain"),
    ("madrid", "Madrid", "Spain"),
    ("malaga", "Málaga", "Spain"),
    ("seville", "Seville", "Spain"),
    ("lisbon", "Lisbon", "Portugal"),
    ("porto", "Porto", "Portugal"),
    ("athens", "Athens", "Greece"),
    ("catania", "Catania", "Italy"),
    ("palma", "Palma de Mallorca", "Spain"),
    ("copenhagen", "Copenhagen", "Denmark"),
    ("stockholm", "Stockholm", "Sweden"),
    ("gothenburg", "Gothenburg", "Sweden"),
    ("oslo", "Oslo", "Norway"),
    ("bergen", "Bergen", "Norway"),
    ("helsinki", "Helsinki", "Finland"),
]

AIRPORTS = [
    ("LJU", "Ljubljana", "Ljubljana", "Slovenia", "ljubljana", True),
    ("ZAG", "Zagreb", "Zagreb", "Croatia", "zagreb", True),
    ("VIE", "Vienna", "Vienna", "Austria", "vienna", True),
    ("GRZ", "Graz", "Graz", "Austria", "graz", True),
    ("BUD", "Budapest", "Budapest", "Hungary", "budapest", True),
    ("TRS", "Trieste", "Trieste", "Italy", "trieste", True),
    ("VCE", "Venice Marco Polo", "Venice", "Italy", "venice", True),
    ("TSF", "Venice Treviso", "Venice", "Italy", "venice", True),
    ("ALC", "Alicante", "Alicante", "Spain", "alicante", False),
    ("VLC", "Valencia", "Valencia", "Spain", "valencia", False),
    ("BCN", "Barcelona", "Barcelona", "Spain", "barcelona", False),
    ("MAD", "Madrid", "Madrid", "Spain", "madrid", False),
    ("AGP", "Málaga", "Málaga", "Spain", "malaga", False),
    ("SVQ", "Seville", "Seville", "Spain", "seville", False),
    ("LIS", "Lisbon", "Lisbon", "Portugal", "lisbon", False),
    ("OPO", "Porto", "Porto", "Portugal", "porto", False),
    ("ATH", "Athens", "Athens", "Greece", "athens", False),
    ("CTA", "Catania", "Catania", "Italy", "catania", False),
    ("PMI", "Palma de Mallorca", "Palma de Mallorca", "Spain", "palma", False),
    ("CPH", "Copenhagen Kastrup", "Copenhagen", "Denmark", "copenhagen", False),
    ("ARN", "Stockholm Arlanda", "Stockholm", "Sweden", "stockholm", False),
    ("GOT", "Gothenburg Landvetter", "Gothenburg", "Sweden", "gothenburg", False),
    ("OSL", "Oslo Gardermoen", "Oslo", "Norway", "oslo", False),
    ("BGO", "Bergen Flesland", "Bergen", "Norway", "bergen", False),
    ("HEL", "Helsinki Vantaa", "Helsinki", "Finland", "helsinki", False),
]

FLIGHTS = [
    ("f001", "VIE", "ALC", "2026-07-12T07:15:00", "2026-07-12T10:05:00", "Ryanair", 39, False),
    ("f002", "VLC", "TRS", "2026-07-18T13:20:00", "2026-07-18T15:15:00", "Ryanair", 46, False),
    ("f003", "ALC", "VIE", "2026-07-18T06:05:00", "2026-07-18T08:45:00", "Wizz Air", 78, True),
    ("f004", "ZAG", "BCN", "2026-07-09T11:45:00", "2026-07-09T14:05:00", "Vueling", 55, True),
    ("f005", "BCN", "VIE", "2026-07-15T16:40:00", "2026-07-15T19:05:00", "Vueling", 62, True),
    ("f006", "VLC", "ZAG", "2026-07-16T09:10:00", "2026-07-16T11:35:00", "Ryanair", 51, False),
    ("f007", "VCE", "OPO", "2026-08-03T08:30:00", "2026-08-03T10:35:00", "Ryanair", 48, False),
    ("f008", "LIS", "BUD", "2026-08-10T12:00:00", "2026-08-10T16:25:00", "Wizz Air", 69, False),
    ("f009", "OPO", "VCE", "2026-08-09T18:30:00", "2026-08-09T22:25:00", "Ryanair", 74, False),
    ("f010", "BUD", "ATH", "2026-07-20T10:15:00", "2026-07-20T13:10:00", "Wizz Air", 42, False),
    ("f011", "ATH", "VIE", "2026-07-26T20:40:00", "2026-07-26T22:05:00", "Aegean", 58, True),
    ("f012", "TRS", "AGP", "2026-07-22T06:35:00", "2026-07-22T09:20:00", "Ryanair", 44, False),
    ("f013", "SVQ", "VIE", "2026-07-28T17:10:00", "2026-07-28T20:05:00", "Ryanair", 57, False),
    ("f014", "AGP", "ZAG", "2026-07-27T07:50:00", "2026-07-27T10:35:00", "Ryanair", 64, False),
    ("f015", "LJU", "PMI", "2026-08-14T14:15:00", "2026-08-14T16:20:00", "Transavia", 59, True),
    ("f016", "PMI", "VCE", "2026-08-20T19:45:00", "2026-08-20T21:35:00", "Ryanair", 49, False),
    ("f017", "GRZ", "CTA", "2026-08-05T05:40:00", "2026-08-05T07:55:00", "Eurowings", 63, False),
    ("f018", "CTA", "BUD", "2026-08-11T21:30:00", "2026-08-11T23:35:00", "Wizz Air", 52, False),
    ("f019", "VIE", "MAD", "2026-08-18T09:25:00", "2026-08-18T12:30:00", "Iberia Express", 66, True),
    ("f020", "MAD", "BUD", "2026-08-24T15:10:00", "2026-08-24T18:15:00", "Ryanair", 71, False),
    ("f021", "TSF", "BCN", "2026-07-31T15:50:00", "2026-07-31T17:40:00", "Ryanair", 38, False),
    ("f022", "BCN", "TRS", "2026-08-06T08:10:00", "2026-08-06T10:00:00", "Ryanair", 59, False),
    ("f023", "VIE", "VLC", "2026-07-13T12:00:00", "2026-07-13T14:35:00", "Wizz Air", 43, False),
    ("f024", "ALC", "TRS", "2026-07-19T10:45:00", "2026-07-19T12:55:00", "Ryanair", 53, False),
    ("f025", "VIE", "BCN", "2026-07-04T05:35:00", "2026-07-04T07:55:00", "Ryanair", 29, False),
    ("f026", "BCN", "BUD", "2026-07-08T21:35:00", "2026-07-09T00:05:00", "Wizz Air", 37, False),
    ("f027", "BUD", "LIS", "2026-08-01T09:05:00", "2026-08-01T12:10:00", "Wizz Air", 84, True),
    ("f028", "OPO", "VIE", "2026-08-08T10:45:00", "2026-08-08T14:50:00", "Ryanair", 68, True),
    ("f029", "TRS", "VCE", "2026-08-12T08:20:00", "2026-08-12T09:10:00", "Sky Alps", 35, False),
    ("f030", "TSF", "ZAG", "2026-08-17T18:10:00", "2026-08-17T19:05:00", "Ryanair", 31, False),
    ("f031", "LJU", "SVQ", "2026-07-05T12:40:00", "2026-07-05T15:35:00", "Transavia", 82, True),
    ("f032", "AGP", "VIE", "2026-07-11T18:25:00", "2026-07-11T21:10:00", "Ryanair", 54, False),
    ("f033", "VCE", "CTA", "2026-08-21T20:50:00", "2026-08-21T22:35:00", "Wizz Air", 45, False),
    ("f034", "CTA", "TSF", "2026-08-27T05:25:00", "2026-08-27T07:15:00", "Ryanair", 41, False),
    ("f035", "ZAG", "ALC", "2026-07-25T19:40:00", "2026-07-25T22:15:00", "Ryanair", 72, False),
    ("f036", "VLC", "VIE", "2026-07-30T07:05:00", "2026-07-30T09:30:00", "Wizz Air", 48, False),
    ("f037", "GRZ", "OPO", "2026-08-06T13:30:00", "2026-08-06T16:25:00", "Eurowings", 91, True),
    ("f038", "LIS", "VCE", "2026-08-13T22:15:00", "2026-08-14T01:55:00", "Ryanair", 59, False),
    ("f039", "BUD", "AGP", "2026-07-14T06:20:00", "2026-07-14T09:35:00", "Wizz Air", 36, False),
    ("f040", "SVQ", "TRS", "2026-07-20T11:10:00", "2026-07-20T14:00:00", "Ryanair", 49, False),
    ("f041", "TRS", "CTA", "2026-07-14T07:00:00", "2026-07-14T08:45:00", "Ryanair", 34, False),
    ("f042", "CTA", "VCE", "2026-07-21T16:15:00", "2026-07-21T18:05:00", "Ryanair", 49, False),
    ("f043", "VIE", "PMI", "2026-08-05T10:25:00", "2026-08-05T12:45:00", "Wizz Air", 44, False),
    ("f044", "PMI", "BUD", "2026-08-12T15:30:00", "2026-08-12T17:50:00", "Ryanair", 55, False),
    ("f045", "ZAG", "AGP", "2026-07-22T09:50:00", "2026-07-22T12:45:00", "Ryanair", 71, True),
    ("f046", "SVQ", "VIE", "2026-07-29T13:10:00", "2026-07-29T16:05:00", "Ryanair", 64, False),
    ("f047", "LJU", "BCN", "2026-08-09T06:10:00", "2026-08-09T08:20:00", "Transavia", 77, True),
    ("f048", "VLC", "LJU", "2026-08-15T17:35:00", "2026-08-15T20:05:00", "Wizz Air", 61, False),
    ("f049", "VCE", "ALC", "2026-07-17T22:10:00", "2026-07-18T00:35:00", "Ryanair", 33, False),
    ("f050", "VLC", "TSF", "2026-07-23T05:20:00", "2026-07-23T07:15:00", "Ryanair", 45, False),
]

TRANSFERS = [
    ("ALC", "VLC", "Alicante", "Valencia", 2.0, 20, "train/bus"),
    ("VLC", "ALC", "Valencia", "Alicante", 2.0, 20, "train/bus"),
    ("OPO", "LIS", "Porto", "Lisbon", 3.0, 25, "train/bus"),
    ("LIS", "OPO", "Lisbon", "Porto", 3.0, 25, "train/bus"),
    ("AGP", "SVQ", "Málaga", "Seville", 2.5, 25, "train/bus"),
    ("SVQ", "AGP", "Seville", "Málaga", 2.5, 25, "train/bus"),
    ("VCE", "TRS", "Venice", "Trieste", 2.0, 18, "train/bus"),
    ("TRS", "VCE", "Trieste", "Venice", 2.0, 18, "train/bus"),
    ("BCN", "VLC", "Barcelona", "Valencia", 3.0, 30, "train/bus"),
    ("VLC", "BCN", "Valencia", "Barcelona", 3.0, 30, "train/bus"),
    ("MAD", "VLC", "Madrid", "Valencia", 2.0, 30, "train/bus"),
    ("VLC", "MAD", "Valencia", "Madrid", 2.0, 30, "train/bus"),
]


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def seed_session(db, include_demo_flights: bool = True) -> None:
    """Seed reference data (areas, airports, transfers) and optionally demo flights.

    Production runs must use include_demo_flights=False: reference data is required
    for the trip builder, but mock fares must never appear in a real deployment.
    """
    area_by_slug = {}
    for slug, name, country in AIRPORT_AREAS:
        area = db.scalar(select(AirportAreaDB).where(AirportAreaDB.slug == slug))
        if not area:
            area = AirportAreaDB(slug=slug, name=name, country=country)
            db.add(area)
        else:
            area.name = name
            area.country = country
        area_by_slug[slug] = area

    db.flush()

    for code, name, city, country, area_slug, is_origin in AIRPORTS:
        airport = db.get(AirportDB, code)
        if not airport:
            airport = AirportDB(code=code)
            db.add(airport)
        airport.name = name
        airport.city = city
        airport.country = country
        airport.area_id = area_by_slug[area_slug].id
        airport.is_user_origin_candidate = is_origin

    if include_demo_flights:
        for flight_id, origin, destination, departure, arrival, airline, price, baggage in FLIGHTS:
            flight = db.get(FlightDB, flight_id)
            if not flight:
                flight = FlightDB(id=flight_id)
                db.add(flight)
            flight.origin_code = origin
            flight.destination_code = destination
            flight.departure_datetime = dt(departure)
            flight.arrival_datetime = dt(arrival)
            flight.airline = airline
            flight.price = price
            flight.currency = "EUR"
            flight.booking_url = None
            flight.baggage_included = baggage
            flight.provider = "mock"

    for from_code, to_code, from_city, to_city, duration, cost, mode in TRANSFERS:
        transfer = db.scalar(
            select(GroundTransferDB)
            .where(GroundTransferDB.from_airport_code == from_code)
            .where(GroundTransferDB.to_airport_code == to_code)
        )
        if not transfer:
            transfer = GroundTransferDB(from_airport_code=from_code, to_airport_code=to_code)
            db.add(transfer)
        transfer.from_city = from_city
        transfer.to_city = to_city
        transfer.duration_hours = duration
        transfer.estimated_cost = cost
        transfer.mode = mode

    db.commit()


def seed_database(include_demo_flights: bool = True) -> None:
    with SessionLocal() as db:
        seed_session(db, include_demo_flights=include_demo_flights)


def remove_demo_flights() -> None:
    """Delete mock fares from an existing database (production cleanup)."""
    with SessionLocal() as db:
        deleted = db.query(FlightDB).filter(FlightDB.provider == "mock").delete()
        db.commit()
        print(f"Removed {deleted} demo flight(s).")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed Triplet reference data.")
    parser.add_argument(
        "--no-demo-flights",
        action="store_true",
        help="Seed airports/areas/transfers only. Required for production.",
    )
    parser.add_argument(
        "--remove-demo-flights",
        action="store_true",
        help="Delete previously seeded mock fares, then exit.",
    )
    args = parser.parse_args()

    if args.remove_demo_flights:
        remove_demo_flights()
    else:
        seed_database(include_demo_flights=not args.no_demo_flights)
        print("Seeded Triplet database" + (" (reference data only)." if args.no_demo_flights else "."))
