from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.ai.intent_parser import parse_trip_intent
from app.db.models import UserTravelProfileDB
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

    return ScoringContext(route_stats=route_stats, profile=profile)


class SearchTripsTool(Tool):
    name = "search_trips"
    description = "Search deterministic same-city and open-jaw trip options."
    input_model = SearchTripsInput
    output_model = SearchTripsOutput

    def run(self, input_data: SearchTripsInput, context: ToolContext) -> SearchTripsOutput:
        request = TripSearchRequest(**input_data.model_dump())
        airports = AirportsRepository(context.db).list_airports()
        flight_search = context.flight_search_service or FlightSearchService(db=context.db)
        flight_result = flight_search.search_candidate_flights_with_metadata(request)
        transfers = TransfersRepository(context.db).list_transfers()
        scoring = build_scoring_context(context, flight_result.flights)
        # A specific requested destination should always yield something, even if
        # it's over budget (flagged, low score). "Anywhere" keeps the budget filter.
        enforce_budget = request.destinationAirports is None
        paired_trips = build_trips(
            request,
            airports=airports,
            flights=flight_result.flights,
            transfers=transfers,
            scoring=scoring,
            enforce_budget=enforce_budget,
        )
        # Augment with round-trip bundles discovered across Europe (city-directions),
        # which avoid one-way pairing gaps and give true round-trip prices. Bundles
        # are same-city by nature, so an explicit multi-city request skips them.
        if request.returnOriginAirports:
            bundle_trips = []
        else:
            bundle_trips = build_round_trip_options(
                flight_search.discover_round_trip_fares(request), request, scoring, enforce_budget=enforce_budget
            )
        trips = merge_trip_options(paired_trips, bundle_trips)

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
