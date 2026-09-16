"""Release regressions against an isolated, migrated PostgreSQL test database.

No production database is accepted. An outer transaction rolls back even when
the application commits its own savepoint.
"""
import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.alerts.schemas import CreateSavedSearchRequest
from app.alerts.service import SavedSearchService
from app.db.models import SavedSearchDB, TripSuggestionDB, UserDB
from app.privacy.service import erase_user


@pytest.fixture
def postgres_session():
    value = os.getenv("TEST_POSTGRES_URL")
    if not value:
        pytest.skip("Separate PostgreSQL release gate; set TEST_POSTGRES_URL")
    url = make_url(value)
    if url.host not in {"localhost", "127.0.0.1"} or url.database not in {"farelin_test", "triplet"}:
        pytest.fail("Only an isolated local PostgreSQL test database is permitted")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


def linked_trip(db):
    user = UserDB(id=str(uuid4()), email=f"release-{uuid4()}@example.com", password_hash="unusable",
                  is_verified=True, is_active=True, plan="free", subscription_status="none")
    db.add(user); db.commit()
    request = CreateSavedSearchRequest(email=user.email, originAirports=["CPH"], destinationRegions=["nordics"],
        startDate="2026-10-01", endDate="2026-10-31", minTripLengthDays=4, maxTripLengthDays=7,
        maxBudget=400, maxGroundTransferHours=4, tripStyle="one city", frequency="weekly")
    watch = SavedSearchService(db).create_user_saved_search(user, request)
    trip = TripSuggestionDB(id=str(uuid4()), user_id=user.id, saved_search_id=watch.id, title="Fixture",
        trip_type="return", origin_airport="CPH", outbound_destination="HEL", final_arrival_airport="CPH",
        start_date=date(2026, 10, 5), end_date=date(2026, 10, 9), nights=4, total_price=123, payload={})
    db.add(trip); db.commit()
    return user, watch, trip


def test_watch_delete_with_generated_trip(postgres_session):
    db = postgres_session
    user, watch, trip = linked_trip(db)
    SavedSearchService(db).delete_user_saved_search(user, watch.id)
    db.refresh(trip)
    assert trip.saved_search_id is None
    assert db.scalar(select(SavedSearchDB.id).where(SavedSearchDB.id == watch.id)) is None


def test_account_erasure_with_generated_watch_trip(postgres_session):
    db = postgres_session
    user, watch, trip = linked_trip(db)
    user_id, watch_id, trip_id = user.id, watch.id, trip.id
    erase_user(db, user)
    for model, id in [(UserDB, user_id), (SavedSearchDB, watch_id), (TripSuggestionDB, trip_id)]:
        assert db.scalar(select(model.id).where(model.id == id)) is None
