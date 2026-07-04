from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models import Flight

# Duffel offers carry their own expires_at; this is only the fallback validity.
DEFAULT_OFFER_VALIDITY_MINUTES = 30


class DuffelMappingResult(BaseModel):
    flights: list[Flight]
    raw_offers_count: int = 0
    mapped_flights_count: int = 0
    skipped_offers_count: int = 0
    warnings: list[str] = []


def map_offer_request_response_to_flights(payload: dict[str, Any]) -> DuffelMappingResult:
    data = payload.get("data") or {}
    offers = data.get("offers") or []
    mapped: list[Flight] = []
    skipped = 0
    for offer in offers:
        flight = map_offer(offer)
        if flight:
            mapped.append(flight)
        else:
            skipped += 1
    warnings = []
    if skipped:
        warnings.append(f"Skipped {skipped} unsupported or malformed Duffel offer(s).")
    return DuffelMappingResult(
        flights=mapped,
        raw_offers_count=len(offers),
        mapped_flights_count=len(mapped),
        skipped_offers_count=skipped,
        warnings=warnings,
    )


def map_offer(offer: dict[str, Any]) -> Flight | None:
    slices = offer.get("slices") or []
    if len(slices) != 1:
        # One-way searches only for now; multi-slice offers need open-jaw mapping.
        return None
    segments = slices[0].get("segments") or []
    if not segments:
        return None

    first, last = segments[0], segments[-1]
    origin = iata_code(first.get("origin"))
    destination = iata_code(last.get("destination"))
    departure = parse_datetime(first.get("departing_at"))
    arrival = parse_datetime(last.get("arriving_at"))
    price = parse_float(offer.get("total_amount"))
    offer_id = offer.get("id")
    if not origin or not destination or not departure or not arrival or price is None or not offer_id:
        return None

    owner = offer.get("owner") or {}
    carrier = (first.get("marketing_carrier") or {}) if isinstance(first.get("marketing_carrier"), dict) else {}
    airline = owner.get("name") or carrier.get("name") or "UNKNOWN"
    observed_at = datetime.utcnow()
    expires_at = parse_datetime(offer.get("expires_at"))
    duration_minutes = int((arrival - departure).total_seconds() // 60)
    return Flight(
        id=f"duffel-{offer_id}",
        origin=origin,
        destination=destination,
        departureDateTime=departure,
        arrivalDateTime=arrival,
        airline=airline,
        price=price,
        currency=offer.get("total_currency") or "EUR",
        baggageIncluded=offer_includes_checked_bag(offer),
        provider="duffel",
        providerOfferId=offer_id,
        stops=max(len(segments) - 1, 0),
        durationMinutes=duration_minutes if duration_minutes > 0 else None,
        isLive=True,
        confidenceLevel="live",
        observedAt=observed_at,
        expiresAt=expires_at,
        rawProviderRef=offer_id,
    )


def offer_includes_checked_bag(offer: dict[str, Any]) -> bool:
    for slice_ in offer.get("slices") or []:
        for segment in slice_.get("segments") or []:
            for passenger in segment.get("passengers") or []:
                for baggage in passenger.get("baggages") or []:
                    if baggage.get("type") == "checked" and (baggage.get("quantity") or 0) > 0:
                        return True
    return False


def iata_code(place: Any) -> str | None:
    if isinstance(place, dict):
        code = place.get("iata_code")
        return str(code).upper() if code else None
    if isinstance(place, str) and len(place) == 3:
        return place.upper()
    return None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
