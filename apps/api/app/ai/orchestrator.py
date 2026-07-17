import logging
import re
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.ai.intent_parser import parse_trip_intent
from app.ai.prompts import TRIPLET_SYSTEM_PROMPT
from app.ai.providers import (
    SUPPORTED_AI_PROVIDERS,
    AIProviderConfigError,
    AIProviderError,
    active_ai_model,
    build_ai_provider,
)
from app.ai.schemas import (
    AIMetadata,
    AIParseOnlyResponse,
    AISearchRequest,
    AISearchResponse,
    SearchPreviewResponse,
)
from app.config import settings
from app.models import TripSearchRequest
from app.tools.base import ToolContext
from app.tools.registry import ToolNotFoundError, ToolRegistry, ToolValidationError
from app.tools.schemas import ParsedTripIntent, SearchTripsOutput


def build_search_preview(message: str, registry: ToolRegistry, context: ToolContext) -> SearchPreviewResponse:
    intent = parse_trip_intent(message)
    if not intent.parsedSearch:
        return SearchPreviewResponse(intent=intent, results=None)

    results = registry.run_tool("search_trips", intent.parsedSearch.model_dump(mode="json"), context)
    return SearchPreviewResponse(intent=intent, results=results)


logger = logging.getLogger(__name__)

# Keep within the free/anonymous plan's 6-origin entitlement, or defaulted
# searches (no origin city named) 402 for logged-out users.
DEFAULT_ORIGINS = ["LJU", "ZAG", "VIE", "BUD", "TRS", "VCE"]
DEFAULT_START_DATE = date(2026, 7, 1)
DEFAULT_END_DATE = date(2026, 8, 31)
ALLOWED_AI_TOOLS = {"get_airports", "search_trips", "estimate_ground_transfer"}
FALLBACK_KNOWN_AIRPORTS = {
    "LJU",
    "ZAG",
    "VIE",
    "GRZ",
    "BUD",
    "TRS",
    "VCE",
    "TSF",
    "ALC",
    "VLC",
    "BCN",
    "MAD",
    "AGP",
    "SVQ",
    "LIS",
    "OPO",
    "ATH",
    "CTA",
    "PMI",
}


def run_ai_search(request: AISearchRequest, registry: ToolRegistry, context: ToolContext) -> AISearchResponse:
    if not settings.ai_enabled:
        return run_rule_based_search(
            request,
            registry,
            context,
            message_prefix="AI is disabled for local development, so I used rule-based parsing.",
            fallback_used=True,
            warnings=["AI unavailable - used rule-based parsing."],
        )

    if settings.ai_provider.lower() not in SUPPORTED_AI_PROVIDERS:
        return run_rule_based_search(
            request,
            registry,
            context,
            message_prefix=f"AI provider '{settings.ai_provider}' is not supported yet, so I used rule-based parsing.",
            fallback_used=True,
            warnings=[f"Unsupported AI provider '{settings.ai_provider}'."],
        )

    latest_search: dict[str, Any] = {}

    def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in ALLOWED_AI_TOOLS:
            raise ToolNotFoundError(f"Tool '{name}' is not allowed for AI search.")
        if name == "search_trips":
            search_request = validate_search_request(arguments, context)
            result = registry.run_tool(name, search_request.model_dump(mode="json"), context)
            latest_search["request"] = search_request
            latest_search["result"] = result
            return compact_tool_result(name, result)
        result = registry.run_tool(name, arguments, context)
        return compact_tool_result(name, result)

    try:
        provider = build_ai_provider()
        result = provider.run_chat_with_tools(
            messages=[
                {"role": "system", "content": TRIPLET_SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(request)},
            ],
            tools=openai_tool_schemas(registry),
            tool_executor=execute_tool,
            max_tool_calls=settings.ai_max_tool_calls,
        )
    except (AIProviderConfigError, AIProviderError, ToolValidationError, ToolNotFoundError, ValidationError, ValueError) as exc:
        logger.warning("ai_search_fallback reason=%s", type(exc).__name__)
        return run_rule_based_search(
            request,
            registry,
            context,
            message_prefix="AI was unavailable, so I used rule-based parsing.",
            fallback_used=True,
            warnings=[str(exc)],
        )

    search_result = latest_search.get("result")
    parsed_request = latest_search.get("request")
    if not search_result:
        try:
            parsed_request = build_trip_search_request(request, parse_trip_intent(request.message), context, use_defaults=True)
            search_result = registry.run_tool("search_trips", parsed_request.model_dump(mode="json"), context)
        except (ValidationError, ToolValidationError, ValueError) as exc:
            return AISearchResponse(
                message=sanitize_ai_message(result.message or "I need a little more detail before searching trips."),
                parsedRequest=None,
                trips=[],
                missingFields=["originAirports", "dateRange", "tripLength", "maxBudget"],
                confidence=None,
                aiMetadata=AIMetadata(
                    aiProvider=settings.ai_provider,
                    model=active_ai_model(),
                    toolCallsUsed=result.toolCallsUsed,
                    fallbackUsed=False,
                    warnings=result.warnings + [str(exc)],
                ),
            )

    output = SearchTripsOutput.model_validate(search_result)
    return AISearchResponse(
        message=sanitize_ai_message(result.message or build_search_message(output)),
        parsedRequest=parsed_request,
        trips=output.trips,
        missingFields=[],
        confidence=None,
        providerMetadata=output.providerMetadata,
        aiMetadata=AIMetadata(
            aiProvider=settings.ai_provider,
            model=active_ai_model(),
            toolCallsUsed=result.toolCallsUsed,
            fallbackUsed=False,
            warnings=result.warnings,
        ),
    )


def run_ai_parse(request: AISearchRequest, registry: ToolRegistry, context: ToolContext) -> AIParseOnlyResponse:
    if settings.ai_enabled:
        try:
            provider = build_ai_provider()
            latest_parse: dict[str, Any] = {}

            def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                if name != "parse_trip_intent":
                    raise ToolNotFoundError("Only parse_trip_intent is allowed for parse-only requests.")
                parsed = registry.run_tool(name, arguments, context)
                latest_parse["intent"] = parsed
                return parsed.model_dump(mode="json")

            provider.run_chat_with_tools(
                messages=[
                    {"role": "system", "content": "Parse the travel request by calling parse_trip_intent. Do not search trips."},
                    {"role": "user", "content": request.message},
                ],
                tools=[tool_schema(registry.get_tool("parse_trip_intent"))],
                tool_executor=execute_tool,
                max_tool_calls=1,
            )
            intent = latest_parse.get("intent") or parse_trip_intent(request.message)
        except (AIProviderConfigError, AIProviderError, ToolValidationError, ToolNotFoundError):
            intent = parse_trip_intent(request.message)
    else:
        intent = parse_trip_intent(request.message)

    return AIParseOnlyResponse(
        parsedRequest=intent.parsedSearch,
        missingFields=intent.missingFields,
        confidence=intent.confidence,
        notes=intent.notes,
    )


def summarize_search(parsed_request, output) -> str:
    """User-facing summary of a completed search — no internal parser details."""
    from app.data.geography import place_city

    trips = output.trips
    if not trips:
        return (
            "I couldn't find fares for that search right now. Try widening the dates, "
            "raising the budget, or adding more airports you'd fly from."
        )
    dests = {t.outboundFlight.destination for t in trips}
    where = f" to {place_city(next(iter(dests))) or next(iter(dests))}" if len(dests) == 1 else ""
    cheapest = min(t.totalPrice for t in trips)
    plural = "s" if len(trips) != 1 else ""
    return f"Found {len(trips)} trip idea{plural}{where}, from €{round(cheapest)}. Best matches first."


def run_rule_based_search(
    request: AISearchRequest,
    registry: ToolRegistry,
    context: ToolContext,
    message_prefix: str,
    fallback_used: bool,
    warnings: list[str],
) -> AISearchResponse:
    intent = parse_trip_intent(request.message)
    try:
        parsed_request = build_trip_search_request(request, intent, context, use_defaults=True)
        result = registry.run_tool("search_trips", parsed_request.model_dump(mode="json"), context)
        output = SearchTripsOutput.model_validate(result)
        return AISearchResponse(
            message=sanitize_ai_message(summarize_search(parsed_request, output)),
            parsedRequest=parsed_request,
            trips=output.trips,
            missingFields=[],
            confidence=intent.confidence,
            providerMetadata=output.providerMetadata,
            aiMetadata=AIMetadata(
                aiProvider="rule-based",
                model="none",
                toolCallsUsed=1,
                fallbackUsed=fallback_used,
                warnings=warnings,
            ),
        )
    except (ValidationError, ToolValidationError, ValueError) as exc:
        return AISearchResponse(
            message=sanitize_ai_message(
                "Tell me a bit more — where you'd fly from, roughly when, and a budget — and I'll search."
            ),
            parsedRequest=None,
            trips=[],
            missingFields=intent.missingFields or ["originAirports", "dateRange", "tripLength", "maxBudget"],
            confidence=intent.confidence,
            aiMetadata=AIMetadata(
                aiProvider="rule-based",
                model="none",
                toolCallsUsed=0,
                fallbackUsed=fallback_used,
                warnings=warnings + [str(exc)],
            ),
        )


def build_trip_search_request(
    request: AISearchRequest,
    intent: ParsedTripIntent,
    context: ToolContext,
    use_defaults: bool,
) -> TripSearchRequest:
    origin_airports = request.originAirports or intent.originAirports or (DEFAULT_ORIGINS if use_defaults else [])
    destination_airports = request.destinationAirports or intent.destinationAirports
    return_origin_airports = request.returnOriginAirports or intent.returnOriginAirports
    start_date = request.startDate or intent.startDate or (DEFAULT_START_DATE if use_defaults else None)
    end_date = request.endDate or intent.endDate or (DEFAULT_END_DATE if use_defaults else None)
    min_days = request.minTripLengthDays or intent.minTripLengthDays or (4 if use_defaults else None)
    max_days = request.maxTripLengthDays or intent.maxTripLengthDays or (8 if use_defaults else None)
    max_budget = request.maxBudget or intent.maxBudget or (180 if use_defaults else None)
    max_transfer = request.maxGroundTransferHours
    if max_transfer is None:
        max_transfer = intent.maxGroundTransferHours if intent.maxGroundTransferHours is not None else 4
    trip_style = request.tripStyle or intent.tripStyle or "surprise me"

    search_request = TripSearchRequest(
        originAirports=[code.upper() for code in origin_airports],
        destinationAirports=[code.upper() for code in destination_airports] if destination_airports else None,
        returnOriginAirports=(
            [code.upper() for code in return_origin_airports] if return_origin_airports else None
        ),
        startDate=start_date,
        endDate=end_date,
        minTripLengthDays=min_days,
        maxTripLengthDays=max_days,
        maxBudget=max_budget,
        maxGroundTransferHours=max_transfer,
        tripStyle=trip_style,
        directOnly=request.directOnly if request.directOnly is not None else intent.directOnly,
        includeBaggage=request.includeBaggage if request.includeBaggage is not None else intent.includeBaggage,
    )
    return validate_search_request(search_request.model_dump(mode="json"), context)


def validate_search_request(raw: dict[str, Any], context: ToolContext) -> TripSearchRequest:
    request = TripSearchRequest.model_validate(raw)
    limit = context.max_origin_airports
    if limit and len(request.originAirports) > limit:
        # The engine (LLM or defaults) chose the origins, so trim to the plan's
        # entitlement instead of failing the whole search.
        request = request.model_copy(update={"originAirports": request.originAirports[:limit]})
    if request.returnOriginAirports:
        # "…back to Budapest" sometimes gets misparsed as the return ORIGIN even
        # though it's the home airport. Flying home from home is meaningless, so
        # drop any overlap with the origins.
        origins = {code.upper() for code in request.originAirports}
        cleaned = [code for code in request.returnOriginAirports if code.upper() not in origins]
        if len(cleaned) != len(request.returnOriginAirports):
            request = request.model_copy(update={"returnOriginAirports": cleaned or None})
    if request.endDate < request.startDate:
        raise ValueError("endDate must be on or after startDate.")
    if (request.endDate - request.startDate).days > 120:
        raise ValueError("AI search date range cannot exceed 120 days.")
    if request.maxTripLengthDays < request.minTripLengthDays:
        raise ValueError("maxTripLengthDays must be greater than or equal to minTripLengthDays.")
    if request.maxBudget < 20 or request.maxBudget > 5000:
        raise ValueError("maxBudget must be between 20 and 5000.")
    if request.maxGroundTransferHours < 0 or request.maxGroundTransferHours > 12:
        raise ValueError("maxGroundTransferHours must be between 0 and 12.")
    if len(request.originAirports) > 12:
        raise ValueError("AI search supports at most 12 origin airports.")

    known = known_airport_codes(context)
    invalid = [code for code in request.originAirports if code not in known]
    if invalid:
        raise ValueError(f"Unknown origin airport code(s): {', '.join(invalid)}.")
    return request


def known_airport_codes(context: ToolContext) -> set[str]:
    try:
        from app.db.repositories.airports_repository import AirportsRepository

        return {airport.code for airport in AirportsRepository(context.db).list_airports()}
    except Exception:  # noqa: BLE001 - validation falls back to built-in MVP airport set.
        return FALLBACK_KNOWN_AIRPORTS


def openai_tool_schemas(registry: ToolRegistry) -> list[dict[str, Any]]:
    return [tool_schema(registry.get_tool(name)) for name in sorted(ALLOWED_AI_TOOLS)]


def tool_schema(tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_model.model_json_schema(),
        },
    }


def compact_tool_result(name: str, result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        dumped = result.model_dump(mode="json")
    else:
        dumped = result
    if name != "search_trips":
        return dumped

    trips = dumped.get("trips", [])[: settings.ai_max_trips_sent_to_model]
    return {
        "trips": [compact_trip(trip) for trip in trips],
        "tripCount": len(dumped.get("trips", [])),
        "providerMetadata": dumped.get("providerMetadata"),
        "providerWarnings": dumped.get("providerWarnings", []),
    }


def compact_trip(trip: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": trip.get("id"),
        "route": compact_route(trip),
        "tripType": trip.get("tripType"),
        "totalPrice": trip.get("totalPrice"),
        "nights": trip.get("nights") or trip.get("tripLengthDays"),
        "score": trip.get("score"),
        "hasGroundTransfer": bool(trip.get("groundTransfer")),
        "tags": trip.get("tags", []),
    }


def compact_route(trip: dict[str, Any]) -> str:
    outbound = trip.get("outboundFlight", {})
    return_flight = trip.get("returnFlight", {})
    return " -> ".join(
        part
        for part in [
            outbound.get("origin"),
            outbound.get("destination"),
            return_flight.get("origin"),
            return_flight.get("destination"),
        ]
        if part
    )


def build_user_message(request: AISearchRequest) -> str:
    structured = request.model_dump(mode="json", exclude_none=True)
    return (
        "User travel request:\n"
        f"{request.message}\n\n"
        "Structured fields supplied by frontend, if any:\n"
        f"{structured}\n\n"
        "Call search_trips with validated arguments before discussing actual trip options."
    )


def build_search_message(output: SearchTripsOutput) -> str:
    if output.trips:
        return f"Found {len(output.trips)} trip option(s) from deterministic search."
    return "No matching trips were found. Try a wider date range, higher budget, or more origin airports."


def sanitize_ai_message(message: str, max_chars: int = 400) -> str:
    cleaned = message.strip()
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"(?:^|\s)\d+[.)]\s+", " ", cleaned)
    cleaned = cleaned.replace("|", " ")
    cleaned = cleaned.translate(str.maketrans("", "", "*_`#"))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) <= max_chars:
        return cleaned

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    summary = " ".join(sentences[:2]).strip()
    if summary and len(summary) <= max_chars:
        return summary

    return cleaned[: max_chars - 1].rstrip(" ,.;:-") + "."
