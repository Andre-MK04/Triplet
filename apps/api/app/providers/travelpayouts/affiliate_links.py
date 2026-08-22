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
        ]
    )
    affiliate_marker = marker if marker is not None else settings.travelpayouts_marker
    if affiliate_marker:
        params.append(("marker", affiliate_marker))
    return f"{settings.travelpayouts_affiliate_base_url.rstrip('/')}/search?{urlencode(params)}"
