from datetime import datetime, timedelta

from app.db.models import CachedRoundTripDB
from app.db.repositories.cached_deals_repository import CachedDealsRepository
from app.providers.travelpayouts.mapper import RoundTripFare


def fare(dest="CPH", price=120.0, seen: datetime | None = None) -> RoundTripFare:
    return RoundTripFare(
        origin="VIE", destination=dest, price=price, currency="EUR",
        departureDate="2026-08-05", returnDate="2026-08-10", airline="SK",
        stops=0, bookingUrl="https://aviasales.com/x", affiliateUrl="https://aviasales.com/x?marker=1",
        observedAt=seen,
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


def test_upsert_takes_the_current_price_not_the_cheapest_ever_seen(db_session):
    """The cache must not keep a bargain the provider has stopped offering.

    Keeping the lowest price ever seen made Triplet quote fares that were gone:
    one Vienna-Rome trip showed at EUR 48 while the provider and Aviasales both
    said EUR 95. A later fetch is the provider's current answer, so it wins.
    """
    repo = CachedDealsRepository(db_session)
    repo.upsert_deals([fare("CPH", 200)])
    repo.upsert_deals([fare("CPH", 150)])  # price dropped
    repo.upsert_deals([fare("CPH", 300)])  # ...and then rose again

    rows = db_session.query(CachedRoundTripDB).filter_by(destination_code="CPH").all()
    assert len(rows) == 1  # deduped on route+dates
    assert rows[0].price == 300


def test_upsert_prefers_the_more_recent_sighting_over_the_cheaper_one(db_session):
    repo = CachedDealsRepository(db_session)
    old = datetime(2026, 8, 25)
    new = datetime(2026, 8, 30)

    repo.upsert_deals([fare("CPH", 95, seen=new)])
    repo.upsert_deals([fare("CPH", 48, seen=old)])  # cheaper, but stale

    row = db_session.query(CachedRoundTripDB).filter_by(destination_code="CPH").one()
    assert row.price == 95
    assert row.price_seen_at == new


def test_within_one_batch_the_newest_sighting_wins(db_session):
    repo = CachedDealsRepository(db_session)
    repo.upsert_deals([
        fare("CPH", 48, seen=datetime(2026, 8, 25)),
        fare("CPH", 95, seen=datetime(2026, 8, 30)),
    ])

    row = db_session.query(CachedRoundTripDB).filter_by(destination_code="CPH").one()
    assert row.price == 95


def test_upsert_survives_duplicate_keys_within_one_batch(db_session):
    # Overlapping query codes (ARN + the STO metro code) can yield the same
    # route+dates twice in a single provider response. This used to raise a
    # UNIQUE violation at commit and 503 the whole search.
    repo = CachedDealsRepository(db_session)
    written = repo.upsert_deals([fare("STO", 200), fare("STO", 184), fare("STO", 310)])
    assert written == 1

    rows = db_session.query(CachedRoundTripDB).filter_by(destination_code="STO").all()
    assert len(rows) == 1
    assert rows[0].price == 184  # cheapest of the batch wins


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


def test_worldwide_country_scope_filters_shared_cache_without_provider_call(db_session):
    from datetime import date
    from app.models import TripSearchRequest
    from app.services.flight_search_service import FlightSearchService

    CachedDealsRepository(db_session).upsert_deals([fare("JFK", 520), fare("BCN", 110)])

    class ExplodingProvider:
        name = "travelpayouts"
        def discover_round_trips(self, origins):
            raise AssertionError("fresh broad cache must not call the provider")

    service = FlightSearchService(
        db=db_session,
        provider_name="travelpayouts",
        provider=ExplodingProvider(),
    )
    request = TripSearchRequest(
        originAirports=["VIE"], destinationCountries=["US"],
        startDate=date(2026, 8, 1), endDate=date(2026, 8, 31),
        minTripLengthDays=3, maxTripLengthDays=10, maxBudget=700,
        maxGroundTransferHours=4, tripStyle="surprise me",
    )
    fares = service.discover_round_trip_fares(request)
    assert [item.destination for item in fares] == ["JFK"]


def test_alert_cache_only_specific_destination_never_calls_route_provider(db_session):
    from datetime import date
    from app.models import TripSearchRequest
    from app.services.flight_search_service import FlightSearchService

    CachedDealsRepository(db_session).upsert_deals([fare("JFK", 520), fare("BCN", 110)])

    class ExplodingProvider:
        name = "travelpayouts"
        def round_trips_for(self, *args, **kwargs):
            raise AssertionError("cache-only alert must not call the provider")

    service = FlightSearchService(
        db=db_session,
        provider_name="travelpayouts",
        provider=ExplodingProvider(),
        cache_only=True,
    )
    request = TripSearchRequest(
        originAirports=["VIE"], destinationAirports=["JFK"],
        startDate=date(2026, 8, 1), endDate=date(2026, 8, 31),
        minTripLengthDays=3, maxTripLengthDays=10, maxBudget=700,
        maxGroundTransferHours=4, tripStyle="one city",
    )
    assert [item.destination for item in service.discover_round_trip_fares(request)] == ["JFK"]


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


def test_hybrid_search_skips_live_provider_when_deals_cache_is_warm(db_session, monkeypatch):
    from datetime import date
    from app.models import TripSearchRequest
    from app.services import flight_search_service as fss
    from app.services.flight_search_service import FlightSearchService

    CachedDealsRepository(db_session).upsert_deals([fare("CPH", 120)])

    def no_live(*args, **kwargs):
        raise AssertionError("live provider must NOT be built when the cache is warm")

    monkeypatch.setattr(fss, "build_live_provider", no_live)
    svc = FlightSearchService(db=db_session, provider_name="hybrid")
    req = TripSearchRequest(
        originAirports=["VIE"], startDate=date(2026, 8, 1), endDate=date(2026, 8, 31),
        minTripLengthDays=3, maxTripLengthDays=10, maxBudget=300,
        maxGroundTransferHours=4, tripStyle="surprise me",
    )
    result = svc.search_candidate_flights_with_metadata(req)
    assert result.metadata.providerUsed == "database"
    assert result.metadata.liveProviderAttempted is False
