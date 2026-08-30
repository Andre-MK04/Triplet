"""Turn a request's destination wishes into concrete things we can ask a provider.

Triplet lets people say "Ireland", "the Nordics", "Asia", "outside Europe" or
"anywhere" — but a fare API only understands places. Before this module those
broad scopes were *filters*: the search served whatever the shared "cheapest
from your airports" cache happened to hold and then removed everything outside
the scope, so any country the cache didn't already contain returned nothing.

Resolving the scope up front fixes that. A scope becomes a small, ranked list of
query targets (city/airport codes and ISO country codes, which the Travelpayouts
data API accepts as a destination), and the rest of the search keys off the
resolved object instead of re-deriving intent from raw request fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from app.data.country_catalog import countries_by_code, country_catalog
from app.data.flight_places import (
    REGION_TO_COUNTRY_CODES,
    canonical_code,
    catalogue,
    get_place,
)

# Continents are far too big to probe country by country, so a continent (or
# "outside Europe") is narrowed to its best candidates. How many fit depends on
# how many airports the traveller departs from: each origin multiplies the
# queries, and starving origins is as bad as starving destinations.
MIN_COUNTRIES_PER_SCOPE = 3
MAX_COUNTRIES_PER_SCOPE = 12
DEFAULT_REQUEST_BUDGET = 30
NON_EUROPEAN_CONTINENTS = ("Asia", "North America", "Africa", "South America", "Oceania")

ScopeKind = Literal["anywhere", "places", "countries", "mixed"]


@dataclass(frozen=True)
class DestinationScope:
    """What the traveller asked for, expressed as things a provider understands."""

    kind: ScopeKind
    #: Exact city/airport codes the traveller named (depth: many dates each).
    place_codes: tuple[str, ...] = ()
    #: ISO-3166 alpha-2 codes to query as a destination (breadth: many cities).
    country_codes: tuple[str, ...] = ()
    #: Human-readable summary of the scope, for explanations and empty states.
    label: str = "anywhere"
    #: True when the scope had to be narrowed to fit the request budget.
    truncated: bool = False
    #: Everything the scope covered before narrowing, for honest messaging.
    considered_country_codes: tuple[str, ...] = field(default=())

    @property
    def is_anywhere(self) -> bool:
        return self.kind == "anywhere"

    @property
    def is_targeted(self) -> bool:
        return self.kind != "anywhere"

    @property
    def query_targets(self) -> tuple[str, ...]:
        """Provider destination values, named places first."""
        return (*self.place_codes, *self.country_codes)

    @property
    def options_per_destination(self) -> int:
        """How many dated options one destination may contribute to the results.

        The broader the ask, the more the answer should be a list of *places*;
        the narrower it is, the more it should be a list of *dates* for the place
        that was named.
        """
        if self.is_anywhere:
            return 1
        if len(self.country_codes) > 2 and not self.place_codes:
            return 2
        return 4


def countries_that_fit(origin_count: int, request_budget: int = DEFAULT_REQUEST_BUDGET) -> int:
    """How many countries one search can afford to ask about."""
    per_origin = request_budget // max(1, origin_count)
    return max(MIN_COUNTRIES_PER_SCOPE, min(MAX_COUNTRIES_PER_SCOPE, per_origin))


def resolve_destination_scope(
    request,
    *,
    ranked_country_hint: tuple[str, ...] = (),
    request_budget: int = DEFAULT_REQUEST_BUDGET,
) -> DestinationScope:
    """Resolve a TripSearchRequest's destination fields into a query scope.

    ``ranked_country_hint`` is an optional preference order (countries we have
    recently seen real fares to from these origins) used to pick which countries
    of a large continent to probe first.
    """
    place_codes = tuple(dict.fromkeys(canonical_code(code) for code in (request.destinationAirports or [])))

    countries: list[str] = [code.strip().upper() for code in request.destinationCountries if code.strip()]
    for region in request.destinationRegions:
        countries.extend(sorted(REGION_TO_COUNTRY_CODES.get(region.strip().casefold(), frozenset())))
    for continent in request.destinationContinents:
        countries.extend(_countries_in_continent(continent))
    if request.excludeEurope and not countries and not place_codes:
        # "Somewhere outside Europe" is a real destination wish, not a filter over
        # a cache that is almost entirely European.
        for continent in NON_EUROPEAN_CONTINENTS:
            countries.extend(_countries_in_continent(continent))

    countries = [code for code in dict.fromkeys(countries) if code in countries_by_code()]
    if request.excludeEurope:
        countries = [code for code in countries if not _is_european_country(code)]

    considered = tuple(countries)
    ranked = _rank_countries(countries, ranked_country_hint)
    selected = ranked[: countries_that_fit(len(request.originAirports), request_budget)]

    if not place_codes and not selected:
        return DestinationScope(kind="anywhere", label=_anywhere_label(request))

    kind: ScopeKind = "mixed" if place_codes and selected else ("places" if place_codes else "countries")
    return DestinationScope(
        kind=kind,
        place_codes=place_codes,
        country_codes=tuple(selected),
        label=_scope_label(request, place_codes, considered),
        truncated=len(considered) > len(selected),
        considered_country_codes=considered,
    )


def _rank_countries(countries: list[str], hint: tuple[str, ...]) -> list[str]:
    """Order candidates by observed relevance first, then by aviation size.

    The hint carries countries we have actually seen fares to from the traveller's
    airports, which beats any static guess. Everything else falls back to how many
    flightable cities the catalogue lists for that country — a rough but honest
    proxy for how much air service it has.
    """
    hint_order = {code: index for index, code in enumerate(hint)}
    sizes = _city_counts_by_country()
    return sorted(
        countries,
        key=lambda code: (hint_order.get(code, len(hint_order)), -sizes.get(code, 0), code),
    )


@lru_cache(maxsize=1)
def _city_counts_by_country() -> dict[str, int]:
    counts: dict[str, int] = {}
    for place in catalogue().places:
        if place.kind == "city":
            counts[place.country_code] = counts.get(place.country_code, 0) + 1
    return counts


@lru_cache(maxsize=16)
def _countries_in_continent(continent: str) -> tuple[str, ...]:
    folded = continent.strip().casefold()
    return tuple(
        country.code
        for country in country_catalog().countries
        if country.continent.casefold() == folded and country.continent != "Antarctica"
    )


def _is_european_country(code: str) -> bool:
    country = countries_by_code().get(code)
    return bool(country and country.continent == "Europe")


def _anywhere_label(request) -> str:
    return "anywhere outside Europe" if request.excludeEurope else "anywhere"


def _scope_label(request, place_codes: tuple[str, ...], countries: tuple[str, ...]) -> str:
    parts: list[str] = []
    for code in place_codes[:3]:
        place = get_place(code)
        parts.append(place.name if place else code)
    if request.destinationRegions:
        parts.extend(region.strip().title() for region in request.destinationRegions[:2])
    if request.destinationContinents:
        parts.extend(continent.strip() for continent in request.destinationContinents[:2])
    if not parts:
        names = [countries_by_code()[code].name for code in countries[:3] if code in countries_by_code()]
        parts.extend(names)
    if not parts:
        return _anywhere_label(request)
    label = ", ".join(dict.fromkeys(parts))
    return f"{label} (outside Europe)" if request.excludeEurope and request.destinationContinents else label
