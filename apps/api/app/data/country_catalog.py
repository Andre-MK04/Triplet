"""Canonical Triplet country definition and stable ISO/geometry mappings."""

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path


@dataclass(frozen=True)
class Country:
    code: str
    alpha3: str
    numeric_code: str
    name: str
    continent: str
    counts_toward_world_total: bool
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CountryCatalog:
    definition: str
    continents: tuple[str, ...]
    countries: tuple[Country, ...]

    @property
    def counted_countries(self) -> tuple[Country, ...]:
        return tuple(country for country in self.countries if country.counts_toward_world_total)

    @property
    def world_total(self) -> int:
        return len(self.counted_countries)


@lru_cache(maxsize=1)
def country_catalog() -> CountryCatalog:
    path = Path(__file__).with_name("country_catalog.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    countries = tuple(
        Country(
            code=row["code"],
            alpha3=row["alpha3"],
            numeric_code=row["numericCode"],
            name=row["name"],
            continent=row["continent"],
            counts_toward_world_total=bool(row["countsTowardWorldTotal"]),
            aliases=tuple(row.get("aliases", [])),
        )
        for row in data["countries"]
    )
    return CountryCatalog(
        definition=data["definition"],
        continents=tuple(data["continents"]),
        countries=countries,
    )


@lru_cache(maxsize=1)
def countries_by_code() -> dict[str, Country]:
    return {country.code: country for country in country_catalog().countries}


@lru_cache(maxsize=1)
def countries_by_numeric_code() -> dict[str, Country]:
    return {country.numeric_code: country for country in country_catalog().countries}


def get_country(code: str) -> Country | None:
    return countries_by_code().get(code.strip().upper())


def search_countries(query: str, limit: int = 30) -> list[Country]:
    needle = query.strip().casefold()
    if not needle:
        return list(country_catalog().countries[:limit])

    def score(country: Country) -> tuple[int, str]:
        names = (country.name, country.code, country.alpha3, *country.aliases)
        folded = [name.casefold() for name in names]
        if needle in {country.code.casefold(), country.alpha3.casefold()}:
            rank = 0
        elif any(name.startswith(needle) for name in folded):
            rank = 1
        elif any(needle in name for name in folded):
            rank = 2
        else:
            rank = 9
        return rank, country.name

    matches = [country for country in country_catalog().countries if score(country)[0] < 9]
    return sorted(matches, key=score)[:limit]
