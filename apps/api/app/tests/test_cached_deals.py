from datetime import datetime, timedelta

from app.db.models import CachedRoundTripDB
from app.db.repositories.cached_deals_repository import CachedDealsRepository
from app.providers.travelpayouts.mapper import RoundTripFare


def fare(dest="CPH", price=120.0) -> RoundTripFare:
    return RoundTripFare(
        origin="VIE", destination=dest, price=price, currency="EUR",
        departureDate="2026-08-05", returnDate="2026-08-10", airline="SK",
        stops=0, bookingUrl="https://aviasales.com/x", affiliateUrl="https://aviasales.com/x?marker=1",
    )


def test_upsert_and_fresh_deals_roundtrip(db_session):
    repo = CachedDealsRepository(db_session)
    written = repo.upsert_deals([fare("CPH", 120), fare("ARN", 140)])
    assert written == 2

    fresh = repo.fresh_deals(["VIE"])
    dests = {f.destination for f in fresh}
    assert dests == {"CPH", "ARN"}
    assert repo.has_fresh(["VIE"]) is True
    assert repo.has_fresh(["ZAG"]) is False  # no deals from that origin


def test_upsert_keeps_cheapest_for_same_route_dates(db_session):
    repo = CachedDealsRepository(db_session)
    repo.upsert_deals([fare("CPH", 200)])
    repo.upsert_deals([fare("CPH", 150)])  # cheaper -> replaces
    repo.upsert_deals([fare("CPH", 300)])  # pricier -> ignored for price

    rows = db_session.query(CachedRoundTripDB).filter_by(destination_code="CPH").all()
    assert len(rows) == 1  # deduped on route+dates
    assert rows[0].price == 150


def test_stale_deals_are_not_served_and_get_pruned(db_session):
    repo = CachedDealsRepository(db_session)
    repo.upsert_deals([fare("CPH", 120)])
    # Age the row beyond the TTL window.
    row = db_session.query(CachedRoundTripDB).first()
    row.observed_at = datetime.utcnow() - timedelta(hours=48)
    db_session.commit()

    assert repo.fresh_deals(["VIE"], ttl_hours=24) == []
    assert repo.has_fresh(["VIE"], ttl_hours=24) is False
    assert repo.prune_stale(ttl_hours=24) == 1
    assert db_session.query(CachedRoundTripDB).count() == 0


def test_anywhere_search_serves_cache_without_calling_provider(db_session):
    from datetime import date
    from app.models import TripSearchRequest
    from app.services.flight_search_service import FlightSearchService

    # Warm the cache with a VIE deal.
    CachedDealsRepository(db_session).upsert_deals([fare("CPH", 120)])

    class ExplodingProvider:
        name = "travelpayouts"
        def discover_round_trips(self, origins):
            raise AssertionError("provider must NOT be called when cache is fresh")

    svc = FlightSearchService(db=db_session, provider_name="travelpayouts", provider=ExplodingProvider())
    req = TripSearchRequest(
        originAirports=["VIE"], startDate=date(2026, 8, 1), endDate=date(2026, 8, 31),
        minTripLengthDays=3, maxTripLengthDays=10, maxBudget=300,
        maxGroundTransferHours=4, tripStyle="surprise me",
    )
    fares = svc.discover_round_trip_fares(req)
    assert any(f.destination == "CPH" for f in fares)  # served from cache, no exception


def test_anywhere_search_calls_provider_and_warms_cache_when_cold(db_session):
    from datetime import date
    from app.models import TripSearchRequest
    from app.services.flight_search_service import FlightSearchService

    class WarmingProvider:
        name = "travelpayouts"
        def discover_round_trips(self, origins):
            return [fare("BCN", 90)]

    svc = FlightSearchService(db=db_session, provider_name="travelpayouts", provider=WarmingProvider())
    req = TripSearchRequest(
        originAirports=["VIE"], startDate=date(2026, 8, 1), endDate=date(2026, 8, 31),
        minTripLengthDays=3, maxTripLengthDays=10, maxBudget=300,
        maxGroundTransferHours=4, tripStyle="surprise me",
    )
    fares = svc.discover_round_trip_fares(req)
    assert any(f.destination == "BCN" for f in fares)
    # Provider result is now cached for the next search.
    assert CachedDealsRepository(db_session).has_fresh(["VIE"]) is True
