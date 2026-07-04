from datetime import datetime, timedelta
from hashlib import sha1
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel

from app.config import settings
from app.models import Flight


class TravelpayoutsMappingResult(BaseModel):
    flights: list[Flight]
    raw_offers_count: int = 0
    mapped_flights_count: int = 0
    skipped_offers_count: int = 0
    deep_links_returned: int = 0
    affiliate_links_generated: int = 0
    warnings: list[str] = []


def map_prices_for_dates_response_to_flights(
    payload: dict[str, Any],
    marker: str | None = None,
) -> TravelpayoutsMappingResult:
    rows = payload.get("data") or []
    currency = str(payload.get("currency") or settings.travelpayouts_currency).upper()
    mapped: list[Flight] = []
    skipped = 0
    deep_links = 0
    affiliate_links = 0
    for row in rows:
        flight = map_price_row(row, currency, marker)
        if not flight:
            skipped += 1
            continue
        if flight.deepLink:
            deep_links += 1
        if flight.affiliateUrl:
            affiliate_links += 1
        mapped.append(flight)

    warnings = []
    if skipped:
        warnings.append(f"Skipped {skipped} incomplete Travelpayouts price row(s).")
    return TravelpayoutsMappingResult(
        flights=mapped,
        raw_offers_count=len(rows),
        mapped_flights_count=len(mapped),
        skipped_offers_count=skipped,
        deep_links_returned=deep_links,
        affiliate_links_generated=affiliate_links,
        warnings=warnings,
    )


def map_price_row(row: dict[str, Any], currency: str, marker: str | None) -> Flight | None:
    origin = code_or_none(row.get("origin") or row.get("origin_airport"))
    destination = code_or_none(row.get("destination") or row.get("destination_airport"))
    departure = parse_datetime(row.get("departure_at"))
    price = parse_float(row.get("price") or row.get("value"))
    duration_minutes = parse_int(row.get("duration_to") or row.get("duration"))
    if not origin or not destination or not departure or price is None or price <= 0:
        return None
    if not duration_minutes or duration_minutes <= 0:
        # Without a duration we cannot state an honest arrival time; skip the row.
        return None

    arrival = departure_plus_minutes(departure, duration_minutes)
    airline = str(row.get("airline") or "UNKNOWN").upper()
    link = build_search_link(row.get("link"), marker)
    observed_at = datetime.utcnow()
    stable = sha1(
        f"{origin}-{destination}-{departure.isoformat()}-{airline}-{price}".encode()
    ).hexdigest()[:12]
    return Flight(
        id=f"travelpayouts-{stable}",
        origin=origin,
        destination=destination,
        departureDateTime=departure,
        arrivalDateTime=arrival,
        airline=airline,
        price=price,
        currency=currency,
        bookingUrl=link,
        baggageIncluded=False,
        provider="travelpayouts",
        providerOfferId=stable,
        deepLink=link,
        affiliateUrl=link if marker else None,
        stops=parse_int(row.get("transfers")) or 0,
        durationMinutes=duration_minutes,
        isLive=False,
        confidenceLevel="indicative",
        observedAt=observed_at,
        rawProviderRef=stable,
    )


def build_search_link(link_path: Any, marker: str | None) -> str | None:
    if not link_path or not isinstance(link_path, str):
        return None
    base = settings.travelpayouts_affiliate_base_url.rstrip("/")
    url = f"{base}{link_path if link_path.startswith('/') else '/' + link_path}"
    if marker:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode({'marker': marker})}"
    return url


def departure_plus_minutes(departure: datetime, minutes: int) -> datetime:
    return departure + timedelta(minutes=minutes)


def code_or_none(value: Any) -> str | None:
    if isinstance(value, str) and 3 <= len(value) <= 4:
        return value.upper()
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


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
