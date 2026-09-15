"""Private, provider-free discovery from observed round-trip cache rows."""

from collections import Counter
from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserCountryDB, UserTravelProfileDB
from app.db.repositories.cached_deals_repository import CachedDealsRepository
from app.models import TripOption, TripSearchRequest
from app.services.trip_builder import build_round_trip_options
from app.services.trip_scoring import ScoringContext


class OpportunityFeed(BaseModel):
    trips: list[TripOption]
    originAirports: list[str]
    source: str = "cached_database"
    isReady: bool
    isStale: bool


def build_opportunity_feed(db: Session, profile: UserTravelProfileDB | None, user_id: str) -> OpportunityFeed:
    origins = list(dict.fromkeys((profile.origin_airports or []) if profile else []))
    if not origins:
        return OpportunityFeed(trips=[], originAirports=[], isReady=False, isStale=False)

    fares, is_stale = CachedDealsRepository(db).opportunity_fares(origins)
    if not fares:
        return OpportunityFeed(trips=[], originAirports=origins, isReady=False, isStale=False)

    budget_bands = {"under_100": 100, "under_200": 200, "under_400": 400}
    budget = profile.absolute_max_budget or budget_bands.get(profile.budget_comfort_zone, 5000)
    today = date.today()
    request = TripSearchRequest(
        originAirports=origins,
        startDate=today,
        endDate=today + timedelta(days=365),
        minTripLengthDays=1,
        maxTripLengthDays=30,
        maxBudget=max(20, min(float(budget), 5000)),
        maxGroundTransferHours=4,
        tripStyle="surprise me",
        tripPlan="return",
    )
    relationships = db.scalars(
        select(UserCountryDB).where(UserCountryDB.user_id == user_id)
    ).all()
    country_states = {
        row.country_code: (
            "lived" if row.lived else "visited" if row.visited else "wishlist" if row.wishlist else "unvisited"
        )
        for row in relationships
    }
    options = build_round_trip_options(
        fares,
        request,
        ScoringContext(profile=profile, country_states=country_states),
        enforce_budget=False,
    )
    # Give someone several destinations to imagine, not twelve date variants
    # of the single cheapest route. All options still come from the cache.
    counts: Counter[str] = Counter()
    selected: list[TripOption] = []
    for trip in sorted(options, key=lambda item: (item.totalPrice, -item.fitScore if item.fitScore is not None else 0)):
        destination = trip.destination.code if trip.destination else trip.outboundFlight.destination
        if counts[destination] >= 2:
            continue
        counts[destination] += 1
        selected.append(trip)
        if len(selected) >= 12:
            break
    return OpportunityFeed(
        trips=selected,
        originAirports=origins,
        isReady=True,
        isStale=is_stale,
    )
