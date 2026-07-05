from dataclasses import dataclass, field

from app.db.models import UserTravelProfileDB
from app.models import ScoreComponent, TripOption, TripSearchRequest

# Route price history only informs the score once it has a minimal sample.
MIN_OBSERVATIONS_FOR_BASELINE = 3

BUDGET_ZONE_AMOUNTS = {"under_100": 100, "under_200": 200, "under_400": 400}


@dataclass
class ScoringContext:
    """Optional inputs that sharpen scoring: price history and the user's profile."""

    route_stats: dict[str, dict] = field(default_factory=dict)
    profile: UserTravelProfileDB | None = None


def route_key(origin: str, destination: str) -> str:
    return f"{origin.upper()}-{destination.upper()}"


def calculate_deal_score(
    trip: TripOption,
    request: TripSearchRequest,
    context: ScoringContext | None = None,
) -> tuple[int, list[ScoreComponent]]:
    """How unusually good this trip's price/quality is, independent of user taste."""
    components: list[ScoreComponent] = []
    score = 100

    def add(label: str, points: int) -> None:
        nonlocal score
        if points != 0:
            components.append(ScoreComponent(label=label, points=points))
        score += points

    price_ratio = trip.totalPrice / request.maxBudget
    if price_ratio <= 0.4:
        pass
    elif price_ratio <= 0.6:
        add("Well under budget", -5)
    elif price_ratio <= 0.8:
        add("Uses most of the budget", -12)
    else:
        add("Close to budget limit", -22)

    if trip.groundTransfer:
        if trip.groundTransfer.durationHours <= 2:
            add("Short ground transfer", -5)
        elif trip.groundTransfer.durationHours <= 4:
            add("Medium ground transfer", -12)
        else:
            add("Long ground transfer", -25)

    if trip.outboundFlight.departureDateTime.hour < 6:
        add("Early outbound departure", -8)
    if trip.outboundFlight.arrivalDateTime.hour >= 23:
        add("Late outbound arrival", -8)
    if trip.returnFlight.departureDateTime.hour < 6:
        add("Early return departure", -8)
    if trip.returnFlight.arrivalDateTime.hour >= 23:
        add("Late return arrival", -8)

    if trip.nights < 3:
        add("Very short trip", -15)
    elif trip.nights > 10:
        add("Long trip uses more budget days", -8)

    if trip.tripType == "open_jaw" and trip.groundTransfer:
        if trip.groundTransfer.durationHours <= 3:
            add("Two cities with an easy transfer", 5)
        else:
            add("Two cities but a hard transfer", -8)

    if request.includeBaggage and (
        not trip.outboundFlight.baggageIncluded or not trip.returnFlight.baggageIncluded
    ):
        add("Baggage not included", -10)

    add_price_history_component(trip, context, add)
    add_stops_component(trip, add)
    add_confidence_component(trip, add)

    return clamp(score), components


def add_price_history_component(trip: TripOption, context: ScoringContext | None, add) -> None:
    if not context or not context.route_stats:
        return
    ratios: list[float] = []
    near_lowest = False
    for flight in (trip.outboundFlight, trip.returnFlight):
        stats = context.route_stats.get(route_key(flight.origin, flight.destination))
        if not stats or stats.get("count", 0) < MIN_OBSERVATIONS_FOR_BASELINE:
            continue
        avg_price = stats.get("avgPrice")
        min_price = stats.get("minPrice")
        if avg_price:
            ratios.append(flight.price / avg_price)
        if min_price and flight.price <= min_price * 1.02:
            near_lowest = True
    if not ratios:
        return
    ratio = sum(ratios) / len(ratios)
    if ratio <= 0.55:
        add("Far below this route's typical observed price", 12)
    elif ratio <= 0.7:
        add("Well below typical observed price", 8)
    elif ratio <= 0.85:
        add("Below typical observed price", 4)
    elif ratio >= 1.2:
        add("Above typical observed price", -10)
    if near_lowest:
        add("Near the lowest price we've observed", 3)


def add_stops_component(trip: TripOption, add) -> None:
    outbound_stops = trip.outboundFlight.stops
    return_stops = trip.returnFlight.stops
    if outbound_stops is None or return_stops is None:
        return
    total_stops = outbound_stops + return_stops
    if total_stops == 0:
        add("Direct both ways", 4)
    elif total_stops == 2:
        add("Two stops in total", -4)
    elif total_stops > 2:
        add("Several stops", -8)


def add_confidence_component(trip: TripOption, add) -> None:
    levels = {trip.outboundFlight.confidenceLevel, trip.returnFlight.confidenceLevel}
    if levels == {"live"}:
        add("Live fares for both flights", 3)


def calculate_fit_score(
    trip: TripOption,
    request: TripSearchRequest,
    profile: UserTravelProfileDB | None = None,
) -> tuple[int, list[ScoreComponent]]:
    """How well this trip matches the user's travel profile (or the request alone)."""
    components: list[ScoreComponent] = []
    score = 70

    def add(label: str, points: int) -> None:
        nonlocal score
        if points != 0:
            components.append(ScoreComponent(label=label, points=points))
        score += points

    if profile is None:
        # Without a profile, fit is relative to the request only.
        middle = (request.minTripLengthDays + request.maxTripLengthDays) / 2
        if abs(trip.nights - middle) <= 1:
            add("Trip length in your sweet spot", 5)
        if trip.totalPrice <= request.maxBudget * 0.6:
            add("Leaves budget for the trip itself", 5)
        return clamp(score), components

    origins = {code.upper() for code in profile.origin_airports or []}
    if origins:
        if trip.outboundFlight.origin in origins:
            add("Departs from one of your airports", 10)
        else:
            add("Departs outside your usual airports", -8)

    if profile.preferred_trip_length_min <= trip.nights <= profile.preferred_trip_length_max:
        add("Matches your preferred trip length", 10)
    else:
        add("Outside your preferred trip length", -8)

    if profile.preferred_months and trip.outboundFlight.departureDateTime.month in profile.preferred_months:
        add("In one of your preferred months", 6)

    rules = set(profile.comfort_rules or [])
    outbound_stops = trip.outboundFlight.stops
    return_stops = trip.returnFlight.stops
    if "direct_only" in rules and outbound_stops is not None and return_stops is not None:
        if outbound_stops + return_stops > 0:
            add("Breaks your direct-only rule", -18)
    if "max_one_stop" in rules and outbound_stops is not None and return_stops is not None:
        if max(outbound_stops, return_stops) > 1:
            add("More stops than your max-one-stop rule", -12)
    if "no_departures_before_6am" in rules and (
        trip.outboundFlight.departureDateTime.hour < 6 or trip.returnFlight.departureDateTime.hour < 6
    ):
        add("Departure before 6am", -8)
    if "no_returns_after_midnight" in rules and trip.returnFlight.arrivalDateTime.hour >= 23:
        add("Return lands very late", -8)
    if "cabin_bag_included" in rules and (
        not trip.outboundFlight.baggageIncluded or not trip.returnFlight.baggageIncluded
    ):
        add("Cabin bag may cost extra", -5)

    if trip.tripType == "open_jaw":
        if profile.open_jaw_willingness == "simple_returns_only":
            add("Open-jaw, but you prefer simple returns", -18)
        elif profile.open_jaw_willingness == "nearby_city_open_jaw":
            if trip.groundTransfer and trip.groundTransfer.durationHours <= 3:
                add("Nearby-city open-jaw, your style", 5)
        else:
            add("Adventurous multi-city, your style", 8)

    zone_amount = BUDGET_ZONE_AMOUNTS.get(profile.budget_comfort_zone)
    if zone_amount is not None:
        if trip.totalPrice <= zone_amount:
            add("Inside your budget comfort zone", 6)
        else:
            add("Above your budget comfort zone", -5)

    return clamp(score), components


def calculate_trip_score(trip: TripOption, request: TripSearchRequest) -> int:
    """Legacy single score; equals the deal score without history/profile context."""
    score, _ = calculate_deal_score(trip, request)
    return score


def clamp(score: int) -> int:
    return max(0, min(100, score))
