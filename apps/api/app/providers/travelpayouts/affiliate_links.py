"""Centralized Aviasales affiliate search-link construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlencode

from app.config import settings


@dataclass(frozen=True)
class ItinerarySegment:
    origin: str
    destination: str
    departure_date: date | datetime | str


def build_aviasales_itinerary_url(
    segments: list[ItinerarySegment],
    *,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    trip_class: str = "Y",
    marker: str | None = None,
) -> str | None:
    """Build the documented DDMM compact route, not an observed fare quote."""
    if not segments:
        return None
    # Official documented compact path. Indexed depart_date query parameters
    # have produced shifted dates in the provider's prefilled multi-city form.
    if len(segments) > 7:
        return None
    segment = segments[0]
    origin, destination = segment.origin.strip().upper(), segment.destination.strip().upper()
    try:
        departure = date.fromisoformat(str(segment.departure_date)[:10])
    except ValueError:
        return None
    if not (origin.isascii() and origin.isalpha() and destination.isascii() and destination.isalpha()
            and len(origin) == len(destination) == 3 and origin != destination):
        return None
    cabin = {"Y": "", "C": "c", "W": "w", "F": "f"}.get(trip_class.upper())
    if cabin is None or not 1 <= adults <= 9 or not 0 <= children <= 9 or not 0 <= infants <= 9:
        return None
    passengers = str(adults) + (str(children) if children or infants else "") + (str(infants) if infants else "")
    route = f"{origin}{departure:%d%m}{destination}"
    previous_destination, previous_date = destination, departure
    for segment in segments[1:]:
        next_origin, next_destination = segment.origin.strip().upper(), segment.destination.strip().upper()
        if not all(code.isascii() and code.isalpha() and len(code) == 3 for code in (next_origin, next_destination)) or next_origin == next_destination:
            return None
        try:
            next_date = date.fromisoformat(str(segment.departure_date)[:10])
        except ValueError:
            return None
        if next_date < previous_date:
            return None
        if previous_destination == next_origin:
            route += f"{next_date:%d%m}{next_destination}"
        else:
            route += f"-{next_origin}{next_date:%d%m}{next_destination}"
        previous_destination, previous_date = next_destination, next_date
    # Complex/disjoint searches retain home: removing it left the last To
    # field blank in the provider UI. Standard symmetric returns omit home.
    if len(segments) == 2 and destination == segments[1].origin.strip().upper() and origin == previous_destination:
        route = route[:-3]
    route += cabin + passengers
    query = {"currency": settings.travelpayouts_currency.lower()}
    affiliate_marker = marker if marker is not None else settings.travelpayouts_marker
    if affiliate_marker:
        query["marker"] = affiliate_marker
    return f"{settings.travelpayouts_affiliate_base_url.rstrip('/')}/search/{route}?{urlencode(query)}"
