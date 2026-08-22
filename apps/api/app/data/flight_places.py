"""Generated global flight-place catalogue and geographic matching helpers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

from app.data.country_catalog import country_catalog


@dataclass(frozen=True)
class FlightPlace:
    code: str
    kind: str
    name: str
    city_code: str | None
    country_code: str
    country_name: str
    continent: str | None
    timezone: str | None
    flightable: bool
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class PlaceCatalogue:
    places: tuple[FlightPlace, ...]
    aliases: dict[str, str]


REGION_TO_COUNTRY_CODES: dict[str, frozenset[str]] = {
    "scandinavia": frozenset({"DK", "NO", "SE"}),
    "nordics": frozenset({"DK", "FI", "IS", "NO", "SE"}),
    "iberia": frozenset({"ES", "PT"}),
    "benelux": frozenset({"BE", "LU", "NL"}),
    "baltics": frozenset({"EE", "LT", "LV"}),
    "balkans": frozenset({"AL", "BA", "BG", "GR", "HR", "ME", "MK", "RO", "RS", "SI", "XK"}),
    "southeast asia": frozenset({"BN", "ID", "KH", "LA", "MM", "MY", "PH", "SG", "TH", "TL", "VN"}),
    "east asia": frozenset({"CN", "HK", "JP", "KP", "KR", "MO", "MN", "TW"}),
    "south asia": frozenset({"AF", "BD", "BT", "IN", "LK", "MV", "NP", "PK"}),
    "central asia": frozenset({"KZ", "KG", "TJ", "TM", "UZ"}),
    "middle east": frozenset({"AE", "BH", "EG", "IL", "IQ", "IR", "JO", "KW", "LB", "OM", "PS", "QA", "SA", "SY", "TR", "YE"}),
    "central america": frozenset({"BZ", "CR", "GT", "HN", "NI", "PA", "SV"}),
    "caribbean": frozenset({"AG", "BB", "BS", "CU", "DM", "DO", "GD", "HT", "JM", "KN", "LC", "TT", "VC"}),
}


@lru_cache(maxsize=1)
def catalogue() -> PlaceCatalogue:
    payload = json.loads(Path(__file__).with_name("flight_places.json").read_text(encoding="utf-8"))
    places = tuple(
        FlightPlace(
            code=row["code"],
            kind=row["kind"],
            name=row["name"],
            city_code=row.get("cityCode"),
            country_code=row["countryCode"],
            country_name=row["countryName"],
            continent=row.get("continent"),
            timezone=row.get("timezone"),
            flightable=bool(row.get("flightable", True)),
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
        )
        for row in payload["places"]
    )
    return PlaceCatalogue(places=places, aliases={k.upper(): v.upper() for k, v in payload.get("aliases", {}).items()})


@lru_cache(maxsize=1)
def places_by_code() -> dict[str, tuple[FlightPlace, ...]]:
    grouped: dict[str, list[FlightPlace]] = {}
    for place in catalogue().places:
        grouped.setdefault(place.code, []).append(place)
    return {code: tuple(rows) for code, rows in grouped.items()}


def canonical_code(code: str) -> str:
    normalized = code.strip().upper()
    return catalogue().aliases.get(normalized, normalized)


def get_place(code: str) -> FlightPlace | None:
    rows = places_by_code().get(canonical_code(code), ())
    return next((row for row in rows if row.kind == "city"), rows[0] if rows else None)


def is_flightable_place(code: str) -> bool:
    return get_place(code) is not None


def is_known_place(code: str) -> bool:
    return get_place(code) is not None


def place_matches_filters(
    code: str,
    *,
    country_codes: set[str] | None = None,
    regions: set[str] | None = None,
    continents: set[str] | None = None,
    exclude_europe: bool = False,
) -> bool:
    place = get_place(code)
    if not place or (exclude_europe and place.continent == "Europe"):
        return False
    if country_codes and place.country_code not in country_codes:
        return False
    if continents and (place.continent or "").casefold() not in {value.casefold() for value in continents}:
        return False
    if regions:
        allowed = set().union(*(REGION_TO_COUNTRY_CODES.get(value.casefold(), frozenset()) for value in regions))
        if not allowed or place.country_code not in allowed:
            return False
    return True


def flightable_city_codes_for_country(country_code: str, limit: int = 20) -> list[str]:
    code = country_code.strip().upper()
    cities = [place.code for place in catalogue().places if place.kind == "city" and place.country_code == code]
    if cities:
        return cities[:limit]
    airports = [place.code for place in catalogue().places if place.kind == "airport" and place.country_code == code]
    return airports[:limit]


def search_places(query: str, limit: int = 20) -> list[FlightPlace]:
    needle = query.strip().casefold()
    if not needle:
        return []

    def rank(place: FlightPlace) -> tuple[int, int, str, str]:
        code = place.code.casefold()
        name = place.name.casefold()
        country = place.country_name.casefold()
        if needle == code:
            tier = 0
        elif code.startswith(needle):
            tier = 1
        elif name.startswith(needle):
            tier = 2
        elif any(word.startswith(needle) for word in name.split()):
            tier = 3
        elif needle in name:
            tier = 4
        elif country.startswith(needle):
            tier = 5
        else:
            tier = 9
        return tier, 0 if place.kind == "city" else 1, place.name, place.code

    rows = [place for place in catalogue().places if rank(place)[0] < 9]
    return sorted(rows, key=rank)[: max(1, min(limit, 50))]


@lru_cache(maxsize=1)
def country_name_index() -> dict[str, str]:
    result: dict[str, str] = {}
    for country in country_catalog().countries:
        for name in (country.name, country.code, country.alpha3, *country.aliases):
            result[name.casefold()] = country.code
    return result
