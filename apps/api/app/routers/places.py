"""Bounded worldwide destination autocomplete backed by static flight data."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.data.country_catalog import search_countries
from app.data.flight_places import (
    REGION_TO_COUNTRY_CODES,
    flightable_city_codes_for_country,
    get_place,
    search_places,
)
from app.data.geography import place_city

router = APIRouter(prefix="/places", tags=["places"])


class FlightPlaceResult(BaseModel):
    code: str
    kind: str
    name: str
    subtitle: str
    city: str | None = None
    countryCode: str | None = None
    countryName: str | None = None
    continent: str | None = None
    searchCodes: list[str] = Field(default_factory=list)


@router.get("/search", response_model=list[FlightPlaceResult])
def search_global_places(
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=12, ge=1, le=30),
) -> list[FlightPlaceResult]:
    query = q.strip()
    folded = query.casefold()
    results: list[tuple[int, FlightPlaceResult]] = []

    for country in search_countries(query, limit=5):
        codes = flightable_city_codes_for_country(country.code, limit=20)
        if not codes:
            continue
        exact = folded in {country.name.casefold(), country.code.casefold(), country.alpha3.casefold()}
        results.append(
            (
                0 if exact else 3,
                FlightPlaceResult(
                    code=country.code,
                    kind="country",
                    name=country.name,
                    subtitle=f"Country · {country.continent}",
                    countryCode=country.code,
                    countryName=country.name,
                    continent=country.continent,
                    searchCodes=codes,
                ),
            )
        )

    for region, country_codes in REGION_TO_COUNTRY_CODES.items():
        if region.startswith(folded) or folded in region:
            results.append(
                (
                    2,
                    FlightPlaceResult(
                        code=region,
                        kind="region",
                        name=region.title(),
                        subtitle=f"Region · {len(country_codes)} countries",
                    ),
                )
            )

    continent_names = ("Africa", "Asia", "Europe", "North America", "South America", "Oceania")
    for continent in continent_names:
        if continent.casefold().startswith(folded) or folded in continent.casefold():
            results.append(
                (
                    2,
                    FlightPlaceResult(
                        code=continent,
                        kind="continent",
                        name=continent,
                        subtitle="Continent",
                        continent=continent,
                    ),
                )
            )

    places = search_places(query, limit=max(limit * 2, 20))
    if query.upper() == "FRU":
        alias = get_place("FRU")
        if alias:
            places = [alias, *[place for place in places if place.code != alias.code]]
    for place in places:
        city = place_city(place.code) or place.name
        label = city if place.kind == "city" else place.name
        results.append(
            (
                1 if place.code.casefold() == folded else 4,
                FlightPlaceResult(
                    code=place.code,
                    kind=place.kind,
                    name=label,
                    subtitle=(
                        f"City · {place.country_name}"
                        if place.kind == "city"
                        else f"Airport · {city}, {place.country_name}"
                    ),
                    city=city,
                    countryCode=place.country_code,
                    countryName=place.country_name,
                    continent=place.continent,
                    searchCodes=[place.code],
                ),
            )
        )

    deduped: dict[tuple[str, str], tuple[int, FlightPlaceResult]] = {}
    for ranked in results:
        key = (ranked[1].kind, ranked[1].code)
        if key not in deduped or ranked[0] < deduped[key][0]:
            deduped[key] = ranked
    ordered = sorted(deduped.values(), key=lambda item: (item[0], item[1].name, item[1].code))
    return [item for _, item in ordered[:limit]]
