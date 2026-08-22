"""Flight geography helpers backed by the generated worldwide place catalogue."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

from app.data.country_catalog import country_catalog
from app.data.flight_places import (
    REGION_TO_COUNTRY_CODES,
    canonical_code,
    catalogue,
    flightable_city_codes_for_country,
    get_place,
)


@dataclass(frozen=True)
class Place:
    code: str
    city: str
    country: str
    lat: float | None = None
    lon: float | None = None


def _city_name(code: str) -> str:
    place = get_place(code)
    if not place:
        return code.upper()
    if place.kind == "city":
        return place.name
    city = get_place(place.city_code or "")
    return city.name if city else place.name


# Compatibility mapping for code that still consumes the original Place shape.
PLACES: dict[str, Place] = {
    code: Place(
        code=code,
        city=_city_name(code),
        country=place.country_name,
        lat=place.latitude,
        lon=place.longitude,
    )
    for code in {row.code for row in catalogue().places}
    if (place := get_place(code)) is not None
}

COUNTRY_ALIASES: dict[str, str] = {
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "holland": "Netherlands",
    "the netherlands": "Netherlands",
    "czech republic": "Czechia",
}
for _country in country_catalog().countries:
    for _alias in _country.aliases:
        COUNTRY_ALIASES[_alias.casefold()] = _country.name

_COUNTRY_CODES_BY_NAME = {country.name.casefold(): country.code for country in country_catalog().countries}
_COUNTRY_NAMES_BY_CODE = {country.code: country.name for country in country_catalog().countries}

REGION_TO_COUNTRIES: dict[str, list[str]] = {
    region: [_COUNTRY_NAMES_BY_CODE[code] for code in codes if code in _COUNTRY_NAMES_BY_CODE]
    for region, codes in REGION_TO_COUNTRY_CODES.items()
}
EUROPEAN_COUNTRIES: set[str] = {
    country.name for country in country_catalog().countries if country.continent == "Europe"
}


def is_european(code: str) -> bool:
    """Return true only when the known place is geographically in Europe."""
    place = get_place(code)
    return bool(place and place.continent == "Europe")


def is_european_country(country_code: str) -> bool:
    country = next(
        (row for row in country_catalog().countries if row.code == country_code.strip().upper()),
        None,
    )
    return bool(country and country.continent == "Europe")


def distance_km(origin: str, destination: str) -> float | None:
    """Great-circle distance between two flight places, in kilometres."""
    a = get_place(origin)
    b = get_place(destination)
    if not a or not b or a.latitude is None or b.latitude is None:
        return None
    radius = 6371.0
    p1, p2 = math.radians(a.latitude), math.radians(b.latitude)
    dphi = math.radians(b.latitude - a.latitude)
    dlambda = math.radians((b.longitude or 0) - (a.longitude or 0))
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def estimate_duration_minutes(origin: str, destination: str) -> int | None:
    km = distance_km(origin, destination)
    if km is None:
        return None
    return int(round(km / 780 * 60)) + 45


def place_country(code: str) -> str | None:
    place = get_place(code)
    return place.country_name if place else None


def place_country_code(code: str) -> str | None:
    place = get_place(code)
    return place.country_code if place else None


def place_continent(code: str) -> str | None:
    place = get_place(code)
    return place.continent if place else None


def place_city(code: str) -> str | None:
    return _city_name(canonical_code(code)) if get_place(code) else None


def scope_matches(code: str, scope: set[str]) -> bool:
    normalized = canonical_code(code)
    normalized_scope = {canonical_code(value) for value in scope}
    if normalized in normalized_scope:
        return True
    place = get_place(normalized)
    if not place:
        return False
    city_code = place.city_code or place.code
    return any(
        candidate and (candidate.city_code or candidate.code) == city_code
        for value in normalized_scope
        if (candidate := get_place(value)) is not None
    )


def airports_for_country(country: str, limit: int = 20) -> list[str]:
    name = COUNTRY_ALIASES.get(country.casefold().strip(), country).casefold()
    country_code = _COUNTRY_CODES_BY_NAME.get(name, country.strip().upper())
    return flightable_city_codes_for_country(country_code, limit=limit)


def airports_for_region(region: str, limit: int = 20) -> list[str]:
    codes: list[str] = []
    for country_code in REGION_TO_COUNTRY_CODES.get(region.casefold().strip(), frozenset()):
        codes.extend(flightable_city_codes_for_country(country_code, limit=max(1, limit - len(codes))))
        if len(codes) >= limit:
            break
    return list(dict.fromkeys(codes))[:limit]


AMBIGUOUS_CITY_NAMES = {"nice", "split", "faro", "reading", "mobile", "orange"}
_DESTINATION_CUE = r"(?:to|in|towards?|visit(?:ing)?|near)\s+(?:the\s+)?"


def resolve_place_names(text: str, limit: int = 20) -> list[str]:
    """Resolve explicit worldwide region, country, city, and IATA mentions."""
    lowered = f" {text.casefold()} "
    codes: list[str] = []

    for token in re.findall(r"\b[a-zA-Z]{3}\b", text):
        if not token.isupper():
            continue
        normalized = canonical_code(token)
        if get_place(normalized):
            codes.append(normalized)

    for region in REGION_TO_COUNTRY_CODES:
        if f" {region} " in lowered:
            codes.extend(airports_for_region(region, limit=limit))

    for country in country_catalog().countries:
        names = (country.name, *country.aliases)
        if any(f" {name.casefold()} " in lowered for name in names):
            codes.extend(flightable_city_codes_for_country(country.code, limit=limit))

    for place in catalogue().places:
        if place.kind != "city" or len(place.name) < 4:
            continue
        city = place.name.casefold()
        if city in AMBIGUOUS_CITY_NAMES:
            if re.search(rf"\b{_DESTINATION_CUE}{re.escape(city)}\b", lowered):
                codes.append(place.code)
        elif f" {city} " in lowered:
            codes.append(place.code)
        if len(dict.fromkeys(codes)) >= limit:
            break

    return list(dict.fromkeys(codes))[:limit]
