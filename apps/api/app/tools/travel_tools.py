import logging
from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.ai.intent_parser import parse_trip_intent
from app.data.flight_places import canonical_code, is_flightable_place, is_supported_origin
from app.data.geography import place_city
from app.db.models import UserCountryDB, UserTravelProfileDB
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.price_observations_repository import PriceObservationsRepository
from app.db.repositories.search_logs_repository import SearchLogsRepository
from app.db.repositories.transfers_repository import TransfersRepository
from app.db.repositories.trip_suggestions_repository import TripSuggestionsRepository
from app.models import Flight, TripSearchRequest
from app.services.flight_search_service import FlightSearchService
from app.services.itinerary_builder import (
    build_itineraries,
    flight_legs,
    plan_route,
    propose_route_stops,
)
from app.services.trip_builder import build_round_trip_options, build_trips, merge_trip_options
from app.services.trip_explainer import build_tags
from app.services.trip_scoring import (
    ScoringContext,
    calculate_deal_score,
    calculate_fit_score,
    route_key,
)
from app.tools.base import Tool, ToolContext
from app.tools.schemas import (
    EstimateGroundTransferInput,
    EstimateGroundTransferOutput,
    ExplainTripInput,
    ExplainTripOutput,
    GetAirportsInput,
    GetAirportsOutput,
    ParseTripIntentInput,
    ParseTripIntentOutput,
    SearchTripsInput,
    SearchTripsOutput,
)


logger = logging.getLogger(__name__)

MAX_PERSISTED_SUGGESTIONS = 12
MAX_ROUTE_STATS_LOOKUPS = 60
# How far past the requested window we will look for a nearest match, and how
# many of those to show. Deliberately modest: these are consolation results.
RELAXED_HORIZON_DAYS = 300
RELAXED_RESULT_LIMIT = 8
# A chained itinerary costs one provider request per leg per month, so only the
# first few origins are planned; each adds a whole route's worth of lookups.
MAX_CHAINED_ORIGINS = 3
MAX_CHAINED_RESULTS = 12


class UnsupportedFlightPlaceError(ValueError):
    pass


def build_scoring_context(context: ToolContext, flights: list[Flight]) -> ScoringContext:
    profile = context.db.get(UserTravelProfileDB, context.user_id) if context.user_id else None

    route_stats: dict[str, dict] = {}
    pairs = {(flight.origin, flight.destination) for flight in flights}
    if pairs:
        observations = PriceObservationsRepository(context.db)
        for origin, destination in sorted(pairs)[:MAX_ROUTE_STATS_LOOKUPS]:
            stats = observations.route_stats(origin, destination)
            if stats["count"]:
                route_stats[route_key(origin, destination)] = stats

    country_states: dict[str, str] = {}
    if context.user_id:
        rows = context.db.scalars(select(UserCountryDB).where(UserCountryDB.user_id == context.user_id)).all()
        for row in rows:
            if row.lived:
                country_states[row.country_code] = "lived"
            elif row.visited:
                country_states[row.country_code] = "visited"
            elif row.wishlist:
                country_states[row.country_code] = "wishlist"

    return ScoringContext(route_stats=route_stats, profile=profile, country_states=country_states)


def build_chained_trips(
    request: TripSearchRequest,
    flight_search: FlightSearchService,
    scoring: ScoringContext,
) -> tuple[list, str | None] | None:
    """Multi-city and open-jaw itineraries, priced hop by hop.

    Returns None when the request is not a chained trip, so the caller falls
    through to the round-trip path. Otherwise returns (trips, note) — an empty
    list means the route genuinely could not be priced, and quietly substituting
    a return trip for the multi-city one somebody asked for would be answering a
    different question.

    When the traveller named cities, those are the route. When they named a
    region — "a multi-city trip to Scandinavia" — the cities are proposed from
    the ones we can actually reach inside that region, so the answer never
    wanders outside the place they asked about.
    """
    if request.tripPlan == "return":
        return None

    note: str | None = None
    all_trips: list = []
    for origin in request.originAirports[:MAX_CHAINED_ORIGINS]:
        candidates, discovered = _routes_for_origin(request, flight_search, origin)
        if not candidates:
            if discovered is not None and not discovered:
                note = note or (
                    f"We could not find enough places with fares in {discovered_scope_label(flight_search, request)} "
                    "to build a route. Try a wider date range or a different region."
                )
            continue
        if request.routeStops is None:
            note = note or _proposal_note(request, candidates)

        legs_by_route = {}
        wanted: list[tuple[str, str]] = []
        for stops in candidates:
            legs = plan_route(request, origin, stops=stops)
            if not legs:
                continue
            legs_by_route[tuple(stops)] = legs
            for leg in flight_legs(legs):
                if leg not in wanted:
                    wanted.append(leg)
        if not wanted:
            continue

        # One fetch for every leg any candidate needs: routes overlap heavily, and
        # paying for the same hop three times would exhaust the request budget
        # before the third proposal was ever priced.
        fares = flight_search.one_way_fares_for(request, wanted)
        if not fares:
            continue
        for legs in legs_by_route.values():
            for trip in build_itineraries(request, origin, legs, fares):
                _finish_itinerary(trip, request, scoring)
                all_trips.append(trip)

    all_trips.sort(key=lambda trip: (-trip.dealScore, -(trip.fitScore or 0), trip.totalPrice))
    return all_trips[:MAX_CHAINED_RESULTS], (note if all_trips else note)


def _routes_for_origin(
    request: TripSearchRequest,
    flight_search: FlightSearchService,
    origin: str,
) -> tuple[list[list[str]], list[str] | None]:
    """Candidate stop lists for one origin, plus what we found reachable.

    The second value is None when the traveller named the cities themselves (so
    nothing was discovered), and a list otherwise — empty meaning the region had
    nothing we could reach.
    """
    if request.routeStops:
        return [list(request.routeStops)], None
    if request.tripPlan == "open_jaw" and request.destinationAirports and request.returnOriginAirports:
        return [[request.destinationAirports[0], request.returnOriginAirports[0]]], None

    # Map out the options first: which places inside the requested region do we
    # actually have fares to? Everything downstream chooses only from these.
    reachable = _reachable_cities(request, flight_search, origin)
    return propose_route_stops(request, origin, reachable), reachable


def _reachable_cities(
    request: TripSearchRequest,
    flight_search: FlightSearchService,
    origin: str,
) -> list[str]:
    """Cities in the requested scope we have seen fares to, cheapest first."""
    probe = request.model_copy(update={"originAirports": [origin], "tripPlan": "return"})
    try:
        fares = flight_search.discover_round_trip_fares(probe)
    except Exception:  # noqa: BLE001 - discovery must never break the search
        logger.exception("route_discovery_failed")
        return []
    seen: dict[str, float] = {}
    for fare in fares:
        code = canonical_code(fare.destination)
        if code not in seen or fare.price < seen[code]:
            seen[code] = fare.price
    return [code for code, _ in sorted(seen.items(), key=lambda item: item[1])]


def discovered_scope_label(flight_search: FlightSearchService, request: TripSearchRequest) -> str:
    try:
        return flight_search.resolve_scope(request).label
    except Exception:  # noqa: BLE001
        return "that region"


def _proposal_note(request: TripSearchRequest, candidates: list[list[str]]) -> str:
    shape = "multi-city" if request.tripPlan == "multi_city" else "open-jaw"
    routes = "; ".join(
        " → ".join(place_city(code) or code for code in stops) for stops in candidates[:3]
    )
    return (
        f"You named a region rather than cities, so Triplet planned the {shape} routes: {routes}. "
        "Only places inside that region were considered."
    )


def _finish_itinerary(trip, request: TripSearchRequest, scoring: ScoringContext) -> None:
    trip.dealScore, trip.dealScoreBreakdown = calculate_deal_score(trip, request, scoring)
    trip.fitScore, trip.fitScoreBreakdown = calculate_fit_score(
        trip, request, scoring.profile if scoring else None, scoring
    )
    trip.score = trip.dealScore
    trip.explanation = describe_itinerary(trip)
    trip.tags = build_tags(trip)
    if trip.totalPrice > request.maxBudget:
        trip.tags.insert(0, "Over budget")
        trip.warnings.insert(0, f"Over your €{request.maxBudget:g} budget at €{trip.totalPrice:g}.")
    if trip.groundEstimate:
        trip.warnings.append(
            "The overland legs are yours to arrange — the times and costs shown are rough "
            "estimates and are not part of the trip price."
        )
    if len([s for s in trip.segments if s.kind == "flight"]) > 2:
        trip.warnings.append(
            "This total is each flight bought as its own one-way ticket. Booking the whole "
            "itinerary as a single multi-city fare usually costs more — check the legs "
            "individually to see the price quoted here."
        )


def describe_itinerary(trip) -> str:
    """Plain summary of where the traveller goes and what the price covers."""
    hops = [segment for segment in trip.segments if segment.kind == "flight"]
    home = trip.segments[0].originCity if trip.segments else trip.outboundFlight.origin
    cities = [stay.city for stay in trip.stays]
    route = " → ".join([home, *cities, home]) if cities else trip.outboundFlight.destination
    nights = ", ".join(f"{stay.nights}n in {stay.city}" for stay in trip.stays)
    ground = ""
    if trip.groundEstimate:
        crossings = [s for s in trip.segments if s.kind == "ground"]
        first = crossings[0]
        ground = (
            f" You cross {first.originCity} → {first.destinationCity} overland"
            f" (~{first.transfer.durationHours:g}h, roughly €{first.transfer.estimatedCost:g}), "
            "which is not included in the price."
        )
    return (
        f"{route} over {trip.nights} nights — {nights}. "
        f"€{round(trip.totalPrice)} covers all {len(hops)} flights.{ground}"
    )


def nearest_matches(
    round_trip_fares,
    request: TripSearchRequest,
    scope,
    scoring: ScoringContext,
    airports,
    transfers,
    flights,
) -> tuple[list, str | None]:
    """Closest real options when a named destination has nothing that fits exactly.

    Travelpayouts serves cached market fares — whatever travellers have recently
    searched — so a thin route can genuinely hold no fare of the requested length.
    Vienna→Dublin has September fares, but only 2–4 night ones; asking for a week
    would otherwise return a bare "no trips", which reads as a Triplet failure
    rather than what it is.

    We already hold fares beyond the requested window (the price calendar answers
    with a wide horizon), so the closest matches cost no extra provider requests.
    They are real fares with their real dates — never the requested trip reshaped
    to look like a match — and the returned note says exactly what was loosened.
    """
    if not round_trip_fares and not flights:
        return [], None

    horizon_start = min(request.startDate, date.today())
    horizon_end = max(request.endDate, date.today()) + timedelta(days=RELAXED_HORIZON_DAYS)
    attempts = [
        (
            request.model_copy(update={"minTripLengthDays": 1, "maxTripLengthDays": 60}),
            f"No {request.minTripLengthDays}–{request.maxTripLengthDays} night trip is on offer for "
            f"{scope.label} in these dates. These are the closest real fares, at other trip lengths.",
        ),
        (
            request.model_copy(update={"startDate": horizon_start, "endDate": horizon_end}),
            f"No {scope.label} trip is on offer in those dates. These are the closest real fares, "
            "on other dates.",
        ),
        (
            request.model_copy(
                update={
                    "minTripLengthDays": 1,
                    "maxTripLengthDays": 60,
                    "startDate": horizon_start,
                    "endDate": horizon_end,
                }
            ),
            f"Nothing matched exactly for {scope.label}. These are the closest real fares we hold, "
            "at other dates and trip lengths.",
        ),
    ]

    for relaxed, note in attempts:
        bundles = build_round_trip_options(round_trip_fares, relaxed, scoring, enforce_budget=False)
        paired = build_trips(
            relaxed,
            airports=airports,
            flights=flights,
            transfers=transfers,
            scoring=scoring,
            enforce_budget=False,
        )
        trips = merge_trip_options(paired, bundles, per_destination_limit=scope.options_per_destination)
        if trips:
            return trips[:RELAXED_RESULT_LIMIT], note
    return [], None


class SearchTripsTool(Tool):
    name = "search_trips"
    description = "Search deterministic same-city and open-jaw trip options."
    input_model = SearchTripsInput
    output_model = SearchTripsOutput

    def run(self, input_data: SearchTripsInput, context: ToolContext) -> SearchTripsOutput:
        request = TripSearchRequest(**input_data.model_dump())
        airport_repository = AirportsRepository(context.db)
        invalid_origins = sorted(
            {code.upper() for code in request.originAirports if not is_supported_origin(code)}
        )
        if invalid_origins:
            raise UnsupportedFlightPlaceError(
                f"Unsupported origin airport(s): {', '.join(invalid_origins)}. "
                "Triplet searches trips departing from Europe, so origins must be European airports."
            )
        request.originAirports = [canonical_code(code) for code in request.originAirports]
        for field_name in ("destinationAirports", "returnOriginAirports"):
            values = getattr(request, field_name) or []
            invalid = sorted(code for code in values if not is_flightable_place(code))
            if invalid:
                raise UnsupportedFlightPlaceError(f"Unknown or non-flightable destination code(s): {', '.join(invalid)}.")
            setattr(request, field_name, [canonical_code(code) for code in values] or None)
        airports = airport_repository.list_airports()
        flight_search = context.flight_search_service or FlightSearchService(db=context.db)
        flight_result = flight_search.search_candidate_flights_with_metadata(request)
        transfers = TransfersRepository(context.db).list_transfers()
        scoring = build_scoring_context(context, flight_result.flights)
        scope = flight_search.resolve_scope(request)
        # A requested destination should always yield something, even if it's
        # over budget (flagged, low score). "Anywhere" keeps the budget filter,
        # because there it only hides options the traveller has alternatives to.
        enforce_budget = scope.is_anywhere
        paired_trips = build_trips(
            request,
            airports=airports,
            flights=flight_result.flights,
            transfers=transfers,
            scoring=scoring,
            enforce_budget=enforce_budget,
        )
        # A chained trip — multi-city, or an open jaw with a named fly-home city —
        # is priced hop by hop from one-way fares, which a round-trip bundle
        # cannot express. Its own builder replaces the pairing path entirely.
        relaxation_note: str | None = None
        chained = build_chained_trips(request, flight_search, scoring)
        if chained is not None:
            trips, relaxation_note = chained
            flight_search.apply_deal_metadata(flight_result.metadata)
        else:
            # Augment with worldwide round-trip bundles from shared discovery
            # data, which avoid one-way pairing gaps and give true round-trip
            # prices. Bundles are same-city by nature.
            round_trip_fares = flight_search.discover_round_trip_fares(request)
            bundle_trips = build_round_trip_options(
                round_trip_fares, request, scoring, enforce_budget=enforce_budget
            )
            flight_search.apply_deal_metadata(flight_result.metadata)
            # Naming a place is a request to compare its dates; a broad scope is
            # a request to compare places, so it keeps fewer per destination.
            trips = merge_trip_options(
                paired_trips,
                bundle_trips,
                per_destination_limit=scope.options_per_destination,
            )

            if not trips and scope.is_targeted:
                trips, relaxation_note = nearest_matches(
                    round_trip_fares, request, scope, scoring, airports, transfers, flight_result.flights
                )

        try:
            TripSuggestionsRepository(context.db).save_trips(
                trips[:MAX_PERSISTED_SUGGESTIONS],
                user_id=context.user_id,
                commit=False,
            )
            SearchLogsRepository(context.db).create_search_log(request, len(trips))
            context.db.commit()
        except SQLAlchemyError:
            context.db.rollback()
            for trip in trips:
                trip.suggestionId = None

        return SearchTripsOutput(
            trips=trips,
            relaxationNote=relaxation_note,
            providerUsed=flight_result.metadata.providerUsed,
            providerWarnings=flight_result.metadata.providerWarnings,
            cachedResultsUsed=flight_result.metadata.cachedResultsUsed,
            providerMetadata=flight_result.metadata,
        )


class GetAirportsTool(Tool):
    name = "get_airports"
    description = "List airports, optionally filtered to origin candidates, country, or text query."
    input_model = GetAirportsInput
    output_model = GetAirportsOutput

    def run(self, input_data: GetAirportsInput, context: ToolContext) -> GetAirportsOutput:
        repository = AirportsRepository(context.db)
        airports = (
            repository.list_origin_candidates()
            if input_data.originCandidatesOnly
            else repository.list_airports()
        )

        if input_data.country:
            country = input_data.country.lower()
            airports = [airport for airport in airports if airport.country.lower() == country]
        if input_data.query:
            query = input_data.query.lower()
            airports = [
                airport
                for airport in airports
                if query in airport.code.lower()
                or query in airport.name.lower()
                or query in airport.city.lower()
            ]

        return GetAirportsOutput(airports=airports)


class EstimateGroundTransferTool(Tool):
    name = "estimate_ground_transfer"
    description = "Check whether a known ground transfer exists between two airports or airport areas."
    input_model = EstimateGroundTransferInput
    output_model = EstimateGroundTransferOutput

    def run(self, input_data: EstimateGroundTransferInput, context: ToolContext) -> EstimateGroundTransferOutput:
        transfer = TransfersRepository(context.db).find_transfer_between_areas_or_airports(
            input_data.fromAirport,
            input_data.toAirport,
        )
        if not transfer:
            return EstimateGroundTransferOutput(
                exists=False,
                transfer=None,
                message=f"No known ground transfer from {input_data.fromAirport} to {input_data.toAirport}.",
            )
        return EstimateGroundTransferOutput(
            exists=True,
            transfer=transfer,
            message=(
                f"Known transfer from {transfer.fromCity} to {transfer.toCity}: "
                f"{transfer.durationHours:g}h, about €{transfer.estimatedCost:g}."
            ),
        )


class ExplainTripTool(Tool):
    name = "explain_trip"
    description = "Return the deterministic explanation, warnings, and tags already attached to a trip."
    input_model = ExplainTripInput
    output_model = ExplainTripOutput

    def run(self, input_data: ExplainTripInput, context: ToolContext) -> ExplainTripOutput:
        return ExplainTripOutput(
            explanation=input_data.trip.explanation,
            warnings=input_data.trip.warnings,
            tags=input_data.trip.tags,
        )


class ParseTripIntentTool(Tool):
    name = "parse_trip_intent"
    description = "Parse a natural-language trip request with a rule-based placeholder parser."
    input_model = ParseTripIntentInput
    output_model = ParseTripIntentOutput

    def run(self, input_data: ParseTripIntentInput, context: ToolContext) -> ParseTripIntentOutput:
        parsed = parse_trip_intent(input_data.message)
        return ParseTripIntentOutput(**parsed.model_dump())


def default_travel_tools() -> list[Tool]:
    return [
        SearchTripsTool(),
        GetAirportsTool(),
        EstimateGroundTransferTool(),
        ExplainTripTool(),
        ParseTripIntentTool(),
    ]
