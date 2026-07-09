"""AI trip itinerary generation.

Turns a chosen deal + the traveller's profile into a feasible, personalised
day-by-day plan. Honesty rules mirror the rest of Triplet: suggestions are ideas
to verify, costs are labelled estimates/ranges (never exact or guaranteed), and
the plan is built strictly around the real arrival/departure times and nights so
it never schedules anything before landing or after the flight home.

Generated once per trip suggestion and cached on the row, so re-viewing is free.
"""

import json
import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.ai.providers import AIProviderError, build_ai_provider
from app.data.destination_styles import STYLE_LABELS
from app.data.geography import place_city, place_country

logger = logging.getLogger(__name__)


class ItineraryItem(BaseModel):
    partOfDay: Literal["morning", "afternoon", "evening", "flexible"] = "flexible"
    title: str
    description: str
    category: str = "general"
    estimatedCost: str = "varies"


class ItineraryDay(BaseModel):
    label: str
    items: list[ItineraryItem] = []


class ItineraryPlan(BaseModel):
    summary: str
    days: list[ItineraryDay] = []
    gettingAround: str | None = None
    extraCostEstimate: str | None = None
    disclaimers: list[str] = []
    generatedAt: str | None = None


class ItineraryUnavailable(RuntimeError):
    """AI is not enabled/configured, so no itinerary can be generated."""


_SCHEMA_HINT = (
    '{"summary": str, "days": [{"label": str, "items": [{"partOfDay": '
    '"morning"|"afternoon"|"evening"|"flexible", "title": str, "description": str, '
    '"category": str, "estimatedCost": str}]}], "gettingAround": str, '
    '"extraCostEstimate": str, "disclaimers": [str]}'
)


def generate_itinerary(trip: dict, profile: dict | None, ai_enabled: bool) -> ItineraryPlan:
    if not ai_enabled:
        raise ItineraryUnavailable("AI itineraries are not enabled in this environment.")
    system, user = _build_prompts(trip, profile)
    provider = build_ai_provider()  # raises AIProviderConfigError if no key
    raw = provider.complete_json(system, user)
    plan = _parse_plan(raw)
    plan.generatedAt = datetime.utcnow().isoformat() + "Z"
    # Always append the standing verification disclaimer.
    disclaimer = "These are suggestions — confirm opening times, prices and availability before you go."
    if disclaimer not in plan.disclaimers:
        plan.disclaimers.append(disclaimer)
    return plan


def _build_prompts(trip: dict, profile: dict | None) -> tuple[str, str]:
    outbound = trip.get("outboundFlight", {})
    inbound = trip.get("returnFlight", {})
    dest_code = outbound.get("destination", "")
    return_from = inbound.get("origin", "")
    dest_city = place_city(dest_code) or dest_code
    dest_country = place_country(dest_code) or ""
    open_jaw = trip.get("tripType") == "open_jaw" or (return_from and return_from != dest_code)

    interests = []
    comfort = []
    budget = None
    if profile:
        interests = [STYLE_LABELS.get(t, t) for t in (profile.get("preferredTripTypes") or [])]
        comfort = profile.get("comfortRules") or []
        budget = profile.get("budgetComfortZone")

    facts = {
        "arriveCity": dest_city,
        "arriveAirport": dest_code,
        "country": dest_country,
        "arrival": outbound.get("arrivalDateTime"),
        "flyHomeFromCity": (place_city(return_from) or return_from) if open_jaw else dest_city,
        "flyHomeFromAirport": return_from,
        "departureHome": inbound.get("departureDateTime"),
        "nights": trip.get("nights"),
        "currency": outbound.get("currency", "EUR"),
        "openJaw": open_jaw,
        "groundTransfer": trip.get("groundTransfer"),
        "travellerInterests": interests or ["general sightseeing"],
        "comfortRules": comfort,
        "budgetComfortZone": budget,
    }

    system = (
        "You are Triplet's trip planner. Produce a concise, feasible day-by-day plan for the trip below, "
        "tailored to the traveller's interests. STRICT RULES:\n"
        "- Respect the exact arrival and departure date-times: schedule nothing before arrival on the first "
        "day or after the flight home on the last day, and leave time to reach the airport.\n"
        "- Keep it realistic for the number of nights and for getting around by foot/public transport.\n"
        "- Tailor strongly to the traveller's interests (e.g. food -> notable local dishes, markets and food "
        "areas; nature -> specific hikes/parks/viewpoints; culture -> museums, architecture, neighbourhoods).\n"
        "- If it is an open-jaw trip (arrive in one city, fly home from another), plan the journey between "
        "them, place it sensibly in the days, and mention the transfer and a rough cost.\n"
        "- COSTS: give rough per-item estimates as ranges in the trip currency, clearly as estimates; never "
        "state exact or guaranteed prices, and never claim bookings/reservations. Use 'Free' or 'varies' when apt.\n"
        "- Everything is a suggestion the traveller must verify. Do not invent precise details you can't be "
        "confident about; prefer well-known places and dish/experience types.\n"
        f"Return ONLY a single JSON object matching this schema: {_SCHEMA_HINT}"
    )
    user = "Plan this trip:\n" + json.dumps(facts, default=str, ensure_ascii=False)
    return system, user


def _parse_plan(raw: str) -> ItineraryPlan:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    try:
        data = json.loads(text)
        return ItineraryPlan.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("itinerary_parse_failed error=%s", type(exc).__name__)
        raise AIProviderError("The itinerary came back in an unexpected format. Please try again.") from exc
