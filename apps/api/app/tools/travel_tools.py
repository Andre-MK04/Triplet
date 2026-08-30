from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.ai.intent_parser import parse_trip_intent
from app.data.flight_places import canonical_code, is_flightable_place, is_supported_origin
from app.db.models import UserCountryDB, UserTravelProfileDB
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.price_observations_repository import PriceObservationsRepository
from app.db.repositories.search_logs_repository import SearchLogsRepository
from app.db.repositories.transfers_repository import TransfersRepository
from app.db.repositories.trip_suggestions_repository import TripSuggestionsRepository
from app.models import Flight, TripSearchRequest
from app.services.flight_search_service import FlightSearchService
from app.services.trip_builder import build_round_trip_options, build_trips, merge_trip_options
from app.services.trip_scoring import ScoringContext, route_key
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


MAX_PERSISTED_SUGGESTIONS = 12
MAX_ROUTE_STATS_LOOKUPS = 60
# How far past the requested window we will look for a nearest match, and how
# many of those to show. Deliberately modest: these are consolation results.
RELAXED_HORIZON_DAYS = 300
RELAXED_RESULT_LIMIT = 8


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
        # Augment with worldwide round-trip bundles from shared discovery data,
        # which avoid one-way pairing gaps and give true round-trip prices. Bundles
        # are same-city by nature, so an explicit multi-city request skips them.
        round_trip_fares: list = []
        if request.returnOriginAirports:
            bundle_trips = []
        else:
            round_trip_fares = flight_search.discover_round_trip_fares(request)
            bundle_trips = build_round_trip_options(
                round_trip_fares, request, scoring, enforce_budget=enforce_budget
            )
            flight_search.apply_deal_metadata(flight_result.metadata)
        # Naming a place is a request to compare its dates; a broad scope is a
        # request to compare places, so it keeps fewer options per destination.
        trips = merge_trip_options(
            paired_trips,
            bundle_trips,
            per_destination_limit=scope.options_per_destination,
        )

        relaxation_note: str | None = None
        if not trips and scope.is_targeted and not request.returnOriginAirports:
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
