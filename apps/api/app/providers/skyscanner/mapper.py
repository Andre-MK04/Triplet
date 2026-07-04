from datetime import datetime
from hashlib import sha1
from typing import Any

from pydantic import BaseModel

from app.models import Flight


class SkyscannerMappingResult(BaseModel):
    flights: list[Flight]
    raw_offers_count: int = 0
    mapped_flights_count: int = 0
    skipped_offers_count: int = 0
    deep_links_returned: int = 0
    warnings: list[str] = []


def map_live_response_to_flights(payload: dict[str, Any]) -> SkyscannerMappingResult:
    content = payload.get("content") or payload
    itineraries = list_values(content.get("itineraries"))
    legs_by_id = values_by_id(content.get("legs"))
    segments_by_id = values_by_id(content.get("segments"))
    places_by_id = values_by_id(content.get("places"))
    carriers_by_id = values_by_id(content.get("carriers"))
    agents_by_id = values_by_id(content.get("agents"))

    mapped: list[Flight] = []
    skipped = 0
    deep_links = 0
    for itinerary in itineraries:
        flight = map_live_itinerary(itinerary, legs_by_id, segments_by_id, places_by_id, carriers_by_id, agents_by_id)
        if not flight:
            skipped += 1
            continue
        if flight.deepLink:
            deep_links += 1
        mapped.append(flight)

    warnings = []
    if skipped:
        warnings.append(f"Skipped {skipped} unsupported or malformed Skyscanner itinerary/itineraries.")
    return SkyscannerMappingResult(
        flights=mapped,
        raw_offers_count=len(itineraries),
        mapped_flights_count=len(mapped),
        skipped_offers_count=skipped,
        deep_links_returned=deep_links,
        warnings=warnings,
    )


def map_indicative_response_to_flights(payload: dict[str, Any]) -> SkyscannerMappingResult:
    # TODO: map Skyscanner Indicative Prices once enabled for broad flexible discovery.
    return SkyscannerMappingResult(flights=[], warnings=["Skyscanner indicative price mapping is not implemented yet."])


def map_live_itinerary(
    itinerary: dict[str, Any],
    legs_by_id: dict[str, dict[str, Any]],
    segments_by_id: dict[str, dict[str, Any]],
    places_by_id: dict[str, dict[str, Any]],
    carriers_by_id: dict[str, dict[str, Any]],
    agents_by_id: dict[str, dict[str, Any]],
) -> Flight | None:
    leg_refs = itinerary.get("legIds") or itinerary.get("legs") or []
    leg = resolve_first(leg_refs, legs_by_id)
    if not leg:
        return None

    segment_refs = leg.get("segmentIds") or leg.get("segments") or []
    resolved_segments = [resolve_ref(ref, segments_by_id) for ref in segment_refs]
    resolved_segments = [segment for segment in resolved_segments if segment]
    first_segment = resolved_segments[0] if resolved_segments else leg
    last_segment = resolved_segments[-1] if resolved_segments else leg

    origin = place_code(first_segment.get("originPlaceId") or first_segment.get("origin"), places_by_id)
    destination = place_code(last_segment.get("destinationPlaceId") or last_segment.get("destination"), places_by_id)
    departure = parse_datetime(first_segment.get("departureDateTime") or first_segment.get("departure"))
    arrival = parse_datetime(last_segment.get("arrivalDateTime") or last_segment.get("arrival"))
    price, deep_link, agent_name = cheapest_pricing_option(itinerary, agents_by_id)
    if not origin or not destination or not departure or not arrival or price is None:
        return None

    carrier_id = first_non_empty(
        first_segment.get("marketingCarrierId"),
        first_segment.get("operatingCarrierId"),
        leg.get("marketingCarrierId"),
        leg.get("carrierId"),
    )
    airline = carrier_name(carrier_id, carriers_by_id) or "UNKNOWN"
    offer_id = string_id(itinerary) or sha1(f"{origin}-{destination}-{departure.isoformat()}-{price}".encode()).hexdigest()[:12]
    stable = sha1(f"{offer_id}-{origin}-{destination}-{departure.isoformat()}".encode()).hexdigest()[:12]
    duration = leg.get("durationInMinutes") or leg.get("durationMinutes")
    stops = max(len(resolved_segments) - 1, 0) if resolved_segments else int(leg.get("stopCount") or 0)
    return Flight(
        id=f"skyscanner-{stable}",
        origin=origin,
        destination=destination,
        departureDateTime=departure,
        arrivalDateTime=arrival,
        airline=airline,
        price=float(price),
        currency="EUR",
        bookingUrl=deep_link,
        baggageIncluded=False,
        provider="skyscanner",
        providerOfferId=offer_id,
        deepLink=deep_link,
        agentName=agent_name,
        stops=stops,
        durationMinutes=int(duration) if duration else None,
        isLive=True,
    )


def cheapest_pricing_option(itinerary: dict[str, Any], agents_by_id: dict[str, dict[str, Any]]) -> tuple[float | None, str | None, str | None]:
    options = itinerary.get("pricingOptions") or itinerary.get("pricing_options") or []
    if isinstance(options, dict):
        options = list_values(options)
    best = None
    best_price = None
    for option in options:
        price = nested_float(option, ["price", "amount"]) or nested_float(option, ["price"]) or nested_float(option, ["amount"])
        if price is None:
            continue
        if best_price is None or price < best_price:
            best_price = price
            best = option
    if not best:
        return None, None, None
    agent_ref = first_from_list(best.get("agentIds") or best.get("agents") or [])
    agent = resolve_ref(agent_ref, agents_by_id) if agent_ref else None
    return best_price, best.get("deepLink") or best.get("deep_link") or best.get("url"), (agent or {}).get("name")


def list_values(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return []


def values_by_id(value: Any) -> dict[str, dict[str, Any]]:
    if isinstance(value, dict):
        rows = {}
        for key, row in value.items():
            if isinstance(row, dict):
                row_id = string_id(row) or str(key)
                rows[row_id] = row
        return rows
    return {string_id(row): row for row in list_values(value) if string_id(row)}


def string_id(value: dict[str, Any]) -> str | None:
    raw = value.get("id") or value.get("entityId") or value.get("itineraryId")
    return str(raw) if raw is not None else None


def resolve_first(refs: Any, by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    ref = first_from_list(refs)
    return resolve_ref(ref, by_id)


def resolve_ref(ref: Any, by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(ref, dict):
        return ref
    return by_id.get(str(ref))


def first_from_list(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value


def place_code(value: Any, places_by_id: dict[str, dict[str, Any]]) -> str | None:
    place = resolve_ref(value, places_by_id)
    if isinstance(place, dict):
        code = place.get("iata") or place.get("iataCode") or place.get("displayCode") or place.get("entityId")
        return str(code).upper() if code else None
    if isinstance(value, str) and len(value) == 3:
        return value.upper()
    return None


def carrier_name(value: Any, carriers_by_id: dict[str, dict[str, Any]]) -> str | None:
    carrier = resolve_ref(value, carriers_by_id)
    if isinstance(carrier, dict):
        return carrier.get("name") or carrier.get("displayCode") or carrier.get("iata")
    return str(value) if value else None


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, dict):
        value = value.get("dateTime") or value.get("localDateTime") or value.get("iso")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def nested_float(value: Any, keys: list[str]) -> float | None:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value:
            return value
    return None
