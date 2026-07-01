from datetime import datetime
from hashlib import sha1
from typing import Any

from pydantic import BaseModel

from app.models import Flight


class AmadeusMappingResult(BaseModel):
    flights: list[Flight]
    raw_offers_count: int = 0
    mapped_flights_count: int = 0
    skipped_offers_count: int = 0
    warnings: list[str] = []


def map_amadeus_offer_to_flights(offer_json: dict[str, Any]) -> list[Flight]:
    itineraries = offer_json.get("itineraries") or []
    if len(itineraries) != 1:
        return []

    segments = itineraries[0].get("segments") or []
    if len(segments) != 1:
        return []

    segment = segments[0]
    try:
        origin = segment["departure"]["iataCode"]
        destination = segment["arrival"]["iataCode"]
        departure = datetime.fromisoformat(segment["departure"]["at"].replace("Z", "+00:00")).replace(tzinfo=None)
        arrival = datetime.fromisoformat(segment["arrival"]["at"].replace("Z", "+00:00")).replace(tzinfo=None)
        airline = (offer_json.get("validatingAirlineCodes") or [segment.get("carrierCode") or "UNKNOWN"])[0]
        total = float(offer_json["price"]["total"])
        currency = offer_json.get("price", {}).get("currency") or "EUR"
    except (KeyError, TypeError, ValueError):
        return []

    stable = sha1(f"{offer_json.get('id')}-{origin}-{destination}-{departure.isoformat()}".encode()).hexdigest()[:12]
    return [
        Flight(
            id=f"amadeus-{stable}",
            origin=origin,
            destination=destination,
            departureDateTime=departure,
            arrivalDateTime=arrival,
            airline=airline,
            price=total,
            currency=currency,
            bookingUrl=None,
            baggageIncluded=False,
            provider="amadeus",
        )
    ]


def map_amadeus_offers_to_flights(payload: dict[str, Any]) -> list[Flight]:
    return map_amadeus_offers(payload).flights


def map_amadeus_offers(payload: dict[str, Any]) -> AmadeusMappingResult:
    flights: list[Flight] = []
    warnings: list[str] = []
    raw_offers = payload.get("data") or []
    skipped = 0
    for offer in raw_offers:
        mapped = map_amadeus_offer_to_flights(offer)
        if not mapped:
            skipped += 1
        flights.extend(mapped)

    if skipped:
        warnings.append(f"Skipped {skipped} unsupported or malformed Amadeus offer(s).")

    return AmadeusMappingResult(
        flights=flights,
        raw_offers_count=len(raw_offers),
        mapped_flights_count=len(flights),
        skipped_offers_count=skipped,
        warnings=warnings,
    )
