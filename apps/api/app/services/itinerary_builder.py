"""Build multi-city and open-jaw trips by pricing every hop separately.

A return trip is one fare. A multi-city trip is a chain — Vienna to Barcelona to
Lisbon and home — and its honest price is the sum of each hop's own fare on the
date it is actually flown. That means choosing dates, not just routes: fly to
Barcelona on the 6th and Lisbon on the 11th and the trip costs one thing; shift
either date and it costs another.

Choosing those dates is a shortest-path problem over (leg, departure date), so
that is how it is solved. Each leg contributes its cheapest fare for a given
date, and a stay of a sensible length has to fit between consecutive legs. The
result is the genuinely cheapest set of dates for the route, not a greedy
leg-by-leg guess that can strand the last hop on an expensive day.

Ground hops (the crossing in an open-jaw trip, or two cities too close to fly
between) get a duration and a rough cost so the traveller can plan around them,
but that cost never enters the trip total: Triplet prices flights, and quoting a
train fare it never looked up would be a number pretending to be a quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.config import settings
from app.data.flight_places import canonical_code, get_place
from app.data.geography import distance_km, estimate_duration_minutes, place_city
from app.models import CityStay, Flight, GroundTransfer, TripOption, TripSearchRequest, TripSegment
from app.providers.travelpayouts.affiliate_links import ItinerarySegment, build_aviasales_itinerary_url
from app.providers.travelpayouts.mapper import OneWayFare

# Below this, two cities are close enough that the crossing is a ground journey
# rather than a flight anyone would book.
GROUND_HOP_MAX_KM = 400.0
# A stay shorter than this is not a visit; longer than this and the traveller
# asked for a different trip.
MIN_NIGHTS_PER_CITY = 2
MAX_NIGHTS_PER_CITY = 21
# How many complete itineraries to return for one route.
MAX_ITINERARIES = 6


@dataclass(frozen=True)
class PlannedLeg:
    """One hop of the route, before dates are chosen."""

    origin: str
    destination: str
    is_ground: bool


@dataclass(frozen=True)
class DatedLeg:
    """One hop with its date and, for a flight, the fare being paid."""

    leg: PlannedLeg
    departure: date
    fare: OneWayFare | None


def plan_route(
    request: TripSearchRequest,
    origin: str,
    stops: list[str] | None = None,
) -> list[PlannedLeg] | None:
    """The ordered hops of the requested trip, before any dates are chosen.

    ``stops`` overrides whatever the request names, which is how a proposed route
    is planned: someone who asks for "a multi-city trip to Scandinavia" has given
    a region, not an itinerary, and the cities are chosen for them.

    Returns None when the request does not describe a chain — a plain return trip
    is priced as a single round-trip fare elsewhere, which is cheaper and more
    accurate than summing two one-ways.
    """
    home = canonical_code(origin)
    if stops is not None:
        stops = [canonical_code(code) for code in stops]
    elif request.tripPlan == "multi_city":
        stops = [canonical_code(code) for code in (request.routeStops or [])]
    elif request.tripPlan == "open_jaw":
        into = (request.destinationAirports or [None])[0]
        out_of = (request.returnOriginAirports or [None])[0]
        if not into or not out_of:
            return None
        stops = [canonical_code(into), canonical_code(out_of)]
    else:
        return None

    stops = [code for index, code in enumerate(stops) if index == 0 or code != stops[index - 1]]
    if len(stops) < 2 or any(code == home for code in stops):
        return None

    legs: list[PlannedLeg] = [PlannedLeg(home, stops[0], is_ground=False)]
    for current, following in zip(stops, stops[1:]):
        legs.append(PlannedLeg(current, following, is_ground=_is_ground_hop(request, current, following)))
    legs.append(PlannedLeg(stops[-1], home, is_ground=False))
    return legs


def _is_ground_hop(request: TripSearchRequest, origin: str, destination: str) -> bool:
    """Whether this hop is one people cross overland rather than fly."""
    if request.tripPlan == "open_jaw":
        # The whole point of an open jaw: fly in to one city, out of another,
        # and make your own way between them.
        return True
    km = distance_km(origin, destination)
    return km is not None and km <= GROUND_HOP_MAX_KM


def flight_legs(legs: list[PlannedLeg]) -> list[tuple[str, str]]:
    """The hops that need fares looked up."""
    return [(leg.origin, leg.destination) for leg in legs if not leg.is_ground]


def build_itineraries(
    request: TripSearchRequest,
    origin: str,
    legs: list[PlannedLeg],
    fares_by_leg: dict[tuple[str, str], list[OneWayFare]],
    limit: int = MAX_ITINERARIES,
) -> list[TripOption]:
    """Cheapest dated itineraries for one planned route."""
    cheapest = _cheapest_fare_per_date(legs, fares_by_leg, request)
    if cheapest is None:
        return []

    dated_routes = _best_dated_routes(request, legs, cheapest, limit)
    trips: list[TripOption] = []
    for dated in dated_routes:
        trip = _to_trip_option(request, origin, dated)
        if trip:
            trips.append(trip)
    return trips


def _cheapest_fare_per_date(
    legs: list[PlannedLeg],
    fares_by_leg: dict[tuple[str, str], list[OneWayFare]],
    request: TripSearchRequest,
) -> dict[int, dict[date, OneWayFare]] | None:
    """For each flight leg, the cheapest fare available on each date.

    None when a flight leg has no fares at all: an itinerary missing a hop cannot
    be priced, and inventing that hop is exactly what this must not do.
    """
    per_leg: dict[int, dict[date, OneWayFare]] = {}
    for index, leg in enumerate(legs):
        if leg.is_ground:
            continue
        best: dict[date, OneWayFare] = {}
        for fare in fares_by_leg.get((leg.origin, leg.destination), []):
            if request.directOnly and (fare.stops or 0) > 0:
                continue
            try:
                departure = date.fromisoformat(fare.departureDate[:10])
            except ValueError:
                continue
            current = best.get(departure)
            if current is None or fare.price < current.price:
                best[departure] = fare
        if not best:
            return None
        per_leg[index] = best
    return per_leg


def _best_dated_routes(
    request: TripSearchRequest,
    legs: list[PlannedLeg],
    cheapest: dict[int, dict[date, OneWayFare]],
    limit: int,
) -> list[list[DatedLeg]]:
    """Choose a date for every hop, minimising the total of the flight fares.

    Solved once per possible departure day: pinning the start makes the trip's
    total length a property of the state, so the requested length is enforced
    while searching rather than filtered for afterwards — which is what a plain
    cheapest-path does, and why it kept returning two-night trips for a
    week-long request. Each start then yields its own best itinerary, so the
    results are genuinely different trips rather than one trip nudged around.
    """
    # Two passes. The first is free to put the nights wherever fares are
    # cheapest, which is the right answer for someone chasing a price but can
    # read as twelve nights in Barcelona and two in Lisbon. The second insists
    # every city gets a comparable share, which is what most people picture when
    # they ask for a two-city trip. Offering both beats guessing which they meant.
    routes: list[list[DatedLeg]] = []
    seen: set[tuple[date, ...]] = set()
    for bounds in (None, _balanced_gap_bounds(request, legs)):
        for start in _start_dates(legs, cheapest, request):
            route = _cheapest_route_from(request, legs, cheapest, start, bounds)
            if not route:
                continue
            key = tuple(dated.departure for dated in route)
            if key in seen:
                continue
            seen.add(key)
            routes.append(route)
    routes.sort(key=_route_cost)
    return routes[:limit]


def _balanced_gap_bounds(request: TripSearchRequest, legs: list[PlannedLeg]) -> tuple[int, int]:
    """Gap range that keeps every city's stay a comparable length."""
    stays = max(1, len(legs) - 1)
    shortest = max(MIN_NIGHTS_PER_CITY, request.minTripLengthDays // stays)
    longest = max(shortest, -(-request.maxTripLengthDays // stays))
    return shortest, longest


def _cheapest_route_from(
    request: TripSearchRequest,
    legs: list[PlannedLeg],
    cheapest: dict[int, dict[date, OneWayFare]],
    start: date,
    gap_bounds: tuple[int, int] | None = None,
) -> list[DatedLeg] | None:
    """Cheapest itinerary that departs on ``start``, or None if none fits.

    ``gap_bounds`` narrows how long each stay may be, which is how the balanced
    pass is expressed: same search, tighter room between hops.
    """
    lowest_gap, highest_gap = gap_bounds or (MIN_NIGHTS_PER_CITY, MAX_NIGHTS_PER_CITY)
    last = len(legs) - 1
    # reached[d] = (cost so far, date the previous leg departed)
    reached: dict[date, tuple[float, date | None]] = {start: (_leg_cost(0, start, cheapest), None)}
    parents: list[dict[date, date | None]] = [{start: None}]

    for index in range(1, len(legs)):
        following: dict[date, tuple[float, date | None]] = {}
        allowed = _leg_dates(index, legs, cheapest, request)
        for previous, (cost_so_far, _) in reached.items():
            for gap in range(lowest_gap, highest_gap + 1):
                departure = previous + timedelta(days=gap)
                elapsed = (departure - start).days
                if elapsed > request.maxTripLengthDays:
                    break
                if index == last and elapsed < request.minTripLengthDays:
                    continue
                if departure not in allowed:
                    continue
                total = cost_so_far + _leg_cost(index, departure, cheapest)
                current = following.get(departure)
                if current is None or total < current[0]:
                    following[departure] = (total, previous)
        if not following:
            return None
        reached = following
        parents.append({departure: previous for departure, (_, previous) in following.items()})

    finish = min(reached, key=lambda day: reached[day][0])
    return _walk(legs, cheapest, parents, finish)


def _start_dates(
    legs: list[PlannedLeg],
    cheapest: dict[int, dict[date, OneWayFare]],
    request: TripSearchRequest,
) -> list[date]:
    return [
        day
        for day in _leg_dates(0, legs, cheapest, request)
        if request.startDate <= day <= request.endDate
    ]


def _leg_dates(
    index: int,
    legs: list[PlannedLeg],
    cheapest: dict[int, dict[date, OneWayFare]],
    request: TripSearchRequest,
) -> set[date] | list[date]:
    """Dates this leg could depart on.

    A flown leg can only depart on a day it has a fare for. A ground hop has no
    fare to constrain it, so any day the surrounding flights allow will do.
    """
    if legs[index].is_ground:
        return _ANY_DATE
    dates = cheapest[index]
    if index == 0:
        return sorted(day for day in dates if request.startDate <= day <= request.endDate)
    return dates


class _AnyDate:
    """Stands in for "no date restriction" on ground hops."""

    def __contains__(self, _value: object) -> bool:
        return True

    def __iter__(self):
        return iter(())


_ANY_DATE = _AnyDate()


def _leg_cost(index: int, departure: date, cheapest: dict[int, dict[date, OneWayFare]]) -> float:
    fare = cheapest.get(index, {}).get(departure)
    return fare.price if fare else 0.0


def _route_cost(route: list[DatedLeg]) -> float:
    return sum(dated.fare.price for dated in route if dated.fare)


def _walk(
    legs: list[PlannedLeg],
    cheapest: dict[int, dict[date, OneWayFare]],
    parents: list[dict[date, date | None]],
    finish: date,
) -> list[DatedLeg] | None:
    dates: list[date] = [finish]
    for index in range(len(legs) - 1, 0, -1):
        previous = parents[index].get(dates[0])
        if previous is None:
            return None
        dates.insert(0, previous)
    return [
        DatedLeg(leg=leg, departure=day, fare=cheapest.get(index, {}).get(day))
        for index, (leg, day) in enumerate(zip(legs, dates))
    ]


def _trip_nights(route: list[DatedLeg]) -> int:
    return (route[-1].departure - route[0].departure).days


def _to_trip_option(request: TripSearchRequest, origin: str, route: list[DatedLeg]) -> TripOption | None:
    """Turn a dated route into a scored, linkable trip."""
    segments: list[TripSegment] = []
    flights: list[Flight] = []
    flight_cost = 0.0
    ground_estimate = 0.0
    has_ground = False

    for dated in route:
        leg = dated.leg
        if leg.is_ground or dated.fare is None:
            transfer = _ground_segment(leg.origin, leg.destination)
            if not transfer:
                return None
            has_ground = True
            ground_estimate += transfer.estimatedCost
            segments.append(
                TripSegment(
                    kind="ground",
                    origin=leg.origin,
                    destination=leg.destination,
                    originCity=place_city(leg.origin) or leg.origin,
                    destinationCity=place_city(leg.destination) or leg.destination,
                    departureDate=dated.departure,
                    transfer=transfer,
                )
            )
            continue

        flight = _to_flight(dated)
        flights.append(flight)
        flight_cost += flight.price
        segments.append(
            TripSegment(
                kind="flight",
                origin=leg.origin,
                destination=leg.destination,
                originCity=place_city(leg.origin) or leg.origin,
                destinationCity=place_city(leg.destination) or leg.destination,
                departureDate=dated.departure,
                flight=flight,
            )
        )

    if len(flights) < 2:
        return None

    nights = _trip_nights(route)
    if nights <= 0 or nights < request.minTripLengthDays or nights > request.maxTripLengthDays:
        return None

    stays = _stays(route)
    booking_url = build_aviasales_itinerary_url(
        [ItinerarySegment(d.leg.origin, d.leg.destination, d.departure) for d in route if not d.leg.is_ground]
    )
    trip_type = "open_jaw" if request.tripPlan == "open_jaw" else "multi_city"

    return TripOption(
        id="mc-" + "-".join(f"{d.leg.origin}{d.departure.isoformat()}" for d in route),
        tripType=trip_type,
        outboundFlight=flights[0],
        returnFlight=flights[-1],
        # The first ground crossing, for callers that still read a single transfer.
        groundTransfer=next((s.transfer for s in segments if s.kind == "ground"), None),
        segments=segments,
        stays=stays,
        flightCost=round(flight_cost, 2),
        groundEstimate=round(ground_estimate, 2) if has_ground else None,
        # Flights only, by design: a ground estimate is for planning, not a quote.
        totalPrice=round(flight_cost, 2),
        tripLengthDays=nights,
        nights=nights,
        score=0,
        fareKind="two_one_ways",
        explanation="",
        warnings=[],
        tags=[],
        bookingUrl=booking_url,
        bookingLabel="Check price" if booking_url else None,
        affiliateUrl=booking_url if booking_url and settings.travelpayouts_marker else None,
        providerDeepLink=booking_url,
        provider="travelpayouts",
        linkType=(
            "affiliate_referral"
            if booking_url and settings.travelpayouts_marker
            else ("provider_deeplink" if booking_url else "none")
        ),
        destination=_destination_metadata(route),
    )


def _to_flight(dated: DatedLeg) -> Flight:
    fare = dated.fare
    assert fare is not None
    duration = fare.durationMinutes or estimate_duration_minutes(fare.origin, fare.destination) or 180
    departure_at = datetime.combine(dated.departure, time(hour=9))
    return Flight(
        id=f"ow-{fare.origin}-{fare.destination}-{fare.departureDate}",
        origin=fare.origin,
        destination=fare.destination,
        departureDateTime=departure_at,
        arrivalDateTime=departure_at + timedelta(minutes=duration),
        airline="Multiple airlines",
        price=fare.price,
        currency=fare.currency,
        provider="travelpayouts",
        stops=fare.stops,
        durationMinutes=duration,
        isLive=False,
        confidenceLevel="indicative",
        observedAt=fare.observedAt,
    )


def _ground_segment(origin: str, destination: str) -> GroundTransfer | None:
    """A rough overland crossing between two cities.

    Estimated from great-circle distance at roughly 80 km/h and €0.10/km — an
    honest ballpark for planning, which is why its cost stays out of the total.
    """
    km = distance_km(origin, destination)
    if km is None:
        return None
    return GroundTransfer(
        fromAirport=origin.upper(),
        toAirport=destination.upper(),
        fromCity=place_city(origin) or origin.upper(),
        toCity=place_city(destination) or destination.upper(),
        durationHours=round(km / 80 + 0.5, 1),
        estimatedCost=float(round(min(150.0, max(15.0, km * 0.10)))),
        mode="ground/self-transfer",
    )


def _stays(route: list[DatedLeg]) -> list[CityStay]:
    stays: list[CityStay] = []
    for current, following in zip(route, route[1:]):
        code = current.leg.destination
        place = get_place(code)
        stays.append(
            CityStay(
                code=code,
                city=place_city(code) or code,
                country=place.country_name if place else "",
                countryCode=place.country_code if place else "",
                arrivalDate=current.departure,
                departureDate=following.departure,
                nights=(following.departure - current.departure).days,
            )
        )
    return stays


def _destination_metadata(route: list[DatedLeg]):
    from app.services.trip_builder import destination_metadata

    return destination_metadata(route[0].leg.destination)


# --- Proposing a route when the traveller named a region rather than cities ---

# How far apart two cities may be and still be crossed overland on an open jaw.
OPEN_JAW_MAX_KM = 900.0
# Closer than this and two "stops" are really one destination.
SAME_PLACE_MAX_KM = 150.0
# Ceilings on the search: each proposal costs provider requests for its legs.
MAX_CANDIDATE_CITIES = 5
MAX_PROPOSED_ROUTES = 3


def propose_route_stops(
    request: TripSearchRequest,
    origin: str,
    reachable: list[str],
) -> list[list[str]]:
    """Candidate itineraries inside the region the traveller asked about.

    "A multi-city trip to Scandinavia" names a region, not a route. ``reachable``
    is the set of cities we have actually seen fares to from this origin, already
    filtered to that region, so a proposal can never wander to Spain — the
    geographic ask is enforced by only ever choosing from inside it.

    Cities are visited in nearest-neighbour order from home, which keeps a route
    from doubling back across the map for no reason.
    """
    home = canonical_code(origin)
    # `reachable` arrives best-first — the cities the region actually flies to,
    # cheapest first. That ranking is what picks WHICH cities; geography only
    # decides the order to visit them in. Choosing by proximity instead put
    # Malmö and Kristiansand in a Scandinavian city-hop ahead of Stockholm,
    # because they happen to sit nearer Vienna.
    pool = _spread_out(
        [
            code
            for code in dict.fromkeys(canonical_code(city) for city in reachable)
            if code != home and get_place(code) is not None
        ]
    )[:MAX_CANDIDATE_CITIES]
    if len(pool) < 2:
        return []

    if request.tripPlan == "open_jaw":
        return _open_jaw_pairs(home, pool)

    routes: list[list[str]] = []
    # Three cities is the archetypal city-hop; two is the safe fallback when the
    # region has thin coverage or a leg turns out to have no fares.
    for size in (3, 2):
        if len(pool) >= size:
            routes.append(_nearest_neighbour_order(home, pool[:size]))
    if len(pool) >= 4:
        # One alternative built from the next-best cities, so the proposals are
        # not all variations on the same opening hop.
        routes.append(_nearest_neighbour_order(home, pool[1:4]))
    return _unique_routes(routes)[:MAX_PROPOSED_ROUTES]


def _spread_out(pool: list[str], minimum_km: float = SAME_PLACE_MAX_KM) -> list[str]:
    """Drop cities so close to a better-ranked one that they are the same stop.

    Malmö and Copenhagen are half an hour apart; a route through both is one
    destination pretending to be two.
    """
    kept: list[str] = []
    for code in pool:
        if any((distance_km(code, other) or float("inf")) < minimum_km for other in kept):
            continue
        kept.append(code)
    return kept


def _open_jaw_pairs(home: str, pool: list[str]) -> list[list[str]]:
    """City pairs close enough that crossing between them overland is sensible.

    Ranked by how good the two cities are, not by how short the crossing is:
    sorting on distance alone paired the region's smallest airports, because the
    obscure ones happen to sit close together.
    """
    rank = {code: index for index, code in enumerate(pool)}
    pairs: list[tuple[int, float, list[str]]] = []
    for first in pool:
        for second in pool:
            if first == second:
                continue
            km = distance_km(first, second)
            if km is None or km > OPEN_JAW_MAX_KM:
                continue
            # Fly to the further city and home from the nearer one, so the
            # overland leg heads back towards home rather than away from it.
            out_km = distance_km(home, first) or 0.0
            back_km = distance_km(home, second) or 0.0
            if out_km < back_km:
                continue
            pairs.append((rank[first] + rank[second], km, [first, second]))
    pairs.sort(key=lambda item: (item[0], item[1]))
    return _unique_routes([route for _, _, route in pairs])[:MAX_PROPOSED_ROUTES]


def _nearest_neighbour_order(home: str, pool: list[str]) -> list[str]:
    remaining = list(pool)
    ordered: list[str] = []
    current = home
    while remaining:
        nearest = min(remaining, key=lambda code: distance_km(current, code) or float("inf"))
        ordered.append(nearest)
        remaining.remove(nearest)
        current = nearest
    return ordered


def _unique_routes(routes: list[list[str]]) -> list[list[str]]:
    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for route in routes:
        key = tuple(route)
        if len(set(route)) != len(route) or key in seen:
            continue
        seen.add(key)
        unique.append(route)
    return unique
