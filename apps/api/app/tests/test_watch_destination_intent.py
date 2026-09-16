from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.alerts.schemas import CreateSavedSearchRequest
from app.alerts.service import SavedSearchService, saved_search_to_trip_request
from app.db.models import SavedSearchDB, UserDB


@pytest.mark.parametrize("scope", [
    {"destinationRegions": ["balkans"]},
    {"destinationRegions": ["nordics"]},
    {"destinationCountries": ["JP", "KR", "CN"]},
    {"routeStops": ["ATH", "SKP", "BEG", "SOF"]},
])
def test_watch_preserves_destination_intent_and_canonical_origins(db_session, scope):
    user = UserDB(id="watch-owner", email="watch-owner@example.test", password_hash="unused", is_verified=True)
    db_session.add(user)
    db_session.commit()
    request = CreateSavedSearchRequest(
        email=user.email, originAirports=["cph", "mmx"],
        startDate=date.today() + timedelta(days=7), endDate=date.today() + timedelta(days=90),
        minTripLengthDays=4, maxTripLengthDays=7, maxBudget=400, maxGroundTransferHours=6,
        tripStyle="surprise me", tripPlan="multi_city", frequency="weekly",
        travelStyles=["nature"], directOnly=True, **scope,
    )
    service = SavedSearchService(db_session)
    response = service.create_user_saved_search(user, request)
    row = db_session.scalar(select(SavedSearchDB).where(SavedSearchDB.id == response.id))
    restored = saved_search_to_trip_request(row)
    assert restored.originAirports == ["CPH", "MMX"]
    assert restored.tripPlan == "multi_city"
    assert restored.travelStyles == ["nature"]
    assert restored.directOnly is True
    assert restored.maxTripLengthDays == 7
    assert response.frequency == "weekly"
    for key, value in scope.items():
        assert getattr(restored, key) == value
    assert response.destinationIntent["kind"] == ("explicit_stops" if "routeStops" in scope else "geographic_area")

    class CaptureRegistry:
        def run_tool(self, name, arguments, context):
            assert name == "search_trips"
            assert context.user_id == user.id
            assert arguments["destinationIntent"] == response.destinationIntent
            assert arguments["originAirports"] == ["CPH", "MMX"]
            for key, value in scope.items():
                assert arguments[key] == value
            return {"trips": []}

    service.registry = CaptureRegistry()
    assert service.preview_user_saved_search(user, row.id).matchingTrips == []
