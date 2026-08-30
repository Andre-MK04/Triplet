from datetime import datetime, timedelta
from hashlib import sha1
import re
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel

from app.config import settings
from app.data.geography import estimate_duration_minutes
from app.models import Flight


class RoundTripFare(BaseModel):
    """A cheapest round trip from city-directions: one bundle price, two dates."""

    origin: str
    destination: str
    price: float
    currency: str = "EUR"
    departureDate: str | None = None
    returnDate: str | None = None
    airline: str | None = None
    stops: int = 0
    bookingUrl: str | None = None
    affiliateUrl: str | None = None
    observedAt: datetime | None = None
    expiresAt: datetime | None = None


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
        # The feed sometimes omits duration; estimate it from distance rather than
        # dropping what may be the cheapest fare. None if we can't estimate.
        duration_minutes = estimate_duration_minutes(origin, destination)
    if not duration_minutes or duration_minutes <= 0:
        return None

    arrival = departure_plus_minutes(departure, duration_minutes)
    airline = str(row.get("airline") or "UNKNOWN").upper()
    link = build_search_link(row.get("link"), marker)
    observed_at = observed_at_from_link(row.get("link"))
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


def map_round_trip_rows(payload: dict[str, Any], marker: str | None) -> list[RoundTripFare]:
    """Round-trip fares from prices_for_dates(one_way=false): reliable per-route
    round trips, so a specifically-requested destination always yields something."""
    rows = payload.get("data") or []
    currency = str(payload.get("currency") or settings.travelpayouts_currency).upper()
    fares: list[RoundTripFare] = []
    for row in rows:
        origin = code_or_none(row.get("origin"))
        destination = code_or_none(row.get("destination"))
        price = parse_float(row.get("price") or row.get("value"))
        return_at = parse_datetime(row.get("return_at"))
        departure = parse_datetime(row.get("departure_at"))
        if not origin or not destination or price is None or price <= 0 or not return_at or not departure:
            continue
        link = build_search_link(row.get("link"), marker)
        fares.append(
            RoundTripFare(
                origin=origin,
                destination=destination,
                price=price,
                currency=currency,
                departureDate=departure.date().isoformat(),
                returnDate=return_at.date().isoformat(),
                airline=(str(row.get("airline")).upper() if row.get("airline") else None),
                stops=parse_int(row.get("transfers")) or 0,
                bookingUrl=link,
                affiliateUrl=link if marker else None,
                observedAt=observed_at_from_link(row.get("link")),
                expiresAt=parse_datetime(row.get("expires_at")),
            )
        )
    return fares


def map_city_directions_response(
    payload: dict[str, Any],
    origin: str,
    marker: str | None,
) -> list[RoundTripFare]:
    """Cheapest round trip per destination from /v1/city-directions."""
    data = payload.get("data") or {}
    currency = str(payload.get("currency") or settings.travelpayouts_currency).upper()
    fares: list[RoundTripFare] = []
    for dest_code, row in data.items():
        destination = code_or_none(row.get("destination") or dest_code)
        price = parse_float(row.get("price") or row.get("value"))
        if not destination or price is None or price <= 0:
            continue
        link = build_search_link(row.get("link"), marker)
        departure = parse_datetime(row.get("departure_at"))
        return_at = parse_datetime(row.get("return_at"))
        fares.append(
            RoundTripFare(
                origin=origin.upper(),
                destination=destination,
                price=price,
                currency=currency,
                departureDate=departure.date().isoformat() if departure else None,
                returnDate=return_at.date().isoformat() if return_at else None,
                airline=(str(row.get("airline")).upper() if row.get("airline") else None),
                stops=parse_int(row.get("transfers")) or 0,
                bookingUrl=link,
                affiliateUrl=link if marker else None,
                observedAt=observed_at_from_link(row.get("link")),
                expiresAt=parse_datetime(row.get("expires_at")),
            )
        )
    return fares


def map_price_calendar_response(
    payload: dict[str, Any],
    origin: str,
    destination: str,
    marker: str | None,
) -> list[RoundTripFare]:
    """Round trips from /v1/prices/calendar, keyed by departure date.

    This is by far the densest per-route source: prices_for_dates returns only a
    handful of round trips per month (five for Vienna→Dublin in September, none
    of them a week long), while the calendar returns the cheapest fare for each
    departure date, covering a real spread of trip lengths.

    Rows carry no booking link, so the caller builds an Aviasales search URL for
    the exact route and dates instead.
    """
    data = payload.get("data") or {}
    currency = str(payload.get("currency") or settings.travelpayouts_currency).upper()
    fares: list[RoundTripFare] = []
    for row in data.values():
        if not isinstance(row, dict):
            continue
        price = parse_float(row.get("price") or row.get("value"))
        departure = parse_datetime(row.get("departure_at"))
        return_at = parse_datetime(row.get("return_at"))
        if price is None or price <= 0 or not departure or not return_at:
            continue
        fares.append(
            RoundTripFare(
                origin=code_or_none(row.get("origin")) or origin.upper(),
                destination=code_or_none(row.get("destination")) or destination.upper(),
                price=price,
                currency=currency,
                departureDate=departure.date().isoformat(),
                returnDate=return_at.date().isoformat(),
                airline=(str(row.get("airline")).upper() if row.get("airline") else None),
                stops=parse_int(row.get("transfers")) or 0,
                bookingUrl=None,
                affiliateUrl=None,
                observedAt=None,
                expiresAt=parse_datetime(row.get("expires_at")),
            )
        )
    return fares


def observed_at_from_link(link_path: Any) -> datetime | None:
    """The date Travelpayouts actually saw this fare, parsed from its own link.

    The data API never returns an observation timestamp, so Triplet used to stamp
    "now" and the UI then told travellers a days-old cached fare had been observed
    just now. The provider's link carries ``search_date=DDMMYYYY`` — the day the
    fare was found — which is the real answer. Returns None when it is absent, and
    the UI says nothing about age rather than guessing.
    """
    if not link_path or not isinstance(link_path, str):
        return None
    match = re.search(r"search_date=(\d{8})", link_path)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d%m%Y")
    except ValueError:
        return None


def build_search_link(link_path: Any, marker: str | None) -> str | None:
    if not link_path or not isinstance(link_path, str):
        return None
    base = settings.travelpayouts_affiliate_base_url.rstrip("/")
    url = f"{base}{link_path if link_path.startswith('/') else '/' + link_path}"
    params: dict[str, str] = {}
    if marker:
        params["marker"] = marker
    # Aviasales prices the landing page in the visitor's own currency unless told
    # otherwise, so a fare we quote as €90 can greet them as $106 — the same
    # money, an unrecognisable number. Quote and destination page must match.
    params["currency"] = settings.travelpayouts_currency.lower()
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params)}"


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
