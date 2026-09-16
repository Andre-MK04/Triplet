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
    """Build a valid indexed multi-city URL for return or open-jaw itineraries."""
    if not segments:
        return None
    # Official documented one-way path. Indexed depart_date query parameters
    # have produced shifted dates in the provider's prefilled multi-city form.
    # Chains use these independently checkable links, not a partial whole-trip link.
    if len(segments) == 1:
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
        route = f"{origin}{departure:%d%m}{destination}{cabin}{passengers}"
        query = {"currency": settings.travelpayouts_currency.lower()}
        affiliate_marker = marker if marker is not None else settings.travelpayouts_marker
        if affiliate_marker:
            query["marker"] = affiliate_marker
        return f"{settings.travelpayouts_affiliate_base_url.rstrip('/')}/search/{route}?{urlencode(query)}"
    params: list[tuple[str, str | int]] = []
    for index, segment in enumerate(segments):
        origin = segment.origin.strip().upper()
        destination = segment.destination.strip().upper()
        if len(origin) != 3 or len(destination) != 3 or origin == destination:
            return None
        value = segment.departure_date
        if isinstance(value, (date, datetime)):
            departure = value.strftime("%Y-%m-%d")
        else:
            try:
                departure = date.fromisoformat(str(value)[:10]).isoformat()
            except ValueError:
                return None
        params.extend(
            [
                (f"segments[{index}][origin_iata]", origin),
                (f"segments[{index}][destination_iata]", destination),
                (f"segments[{index}][depart_date]", departure),
            ]
        )
    params.extend(
        [
            ("adults", max(1, adults)),
            ("children", max(0, children)),
            ("infants", max(0, infants)),
            ("trip_class", trip_class),
            # Without this, Aviasales prices the page in the visitor's own
            # currency, so a fare quoted as €90 can appear as $106 — the same
            # money, but nothing a traveller can reconcile with our number.
            ("currency", settings.travelpayouts_currency.lower()),
        ]
    )
    affiliate_marker = marker if marker is not None else settings.travelpayouts_marker
    if affiliate_marker:
        params.append(("marker", affiliate_marker))
    return f"{settings.travelpayouts_affiliate_base_url.rstrip('/')}/search?{urlencode(params)}"
