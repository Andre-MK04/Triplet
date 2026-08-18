"""European directory-import scope derived from Triplet's country catalog.

Used by the GeoNames/OurAirports import scripts to scope seeding to Europe and
to resolve country names without an extra dataset. Expanding worldwide later
means widening (or dropping) this filter — nothing else assumes Europe.
"""

from app.data.country_catalog import country_catalog

# Directory imports intentionally include European territories and Kosovo even
# though Triplet's configurable 195-country progress definition does not count
# them as separate countries.
EUROPE_DIRECTORY_EXTRAS: dict[str, str] = {
    "FO": "Faroe Islands",
    "GG": "Guernsey",
    "GI": "Gibraltar",
    "IM": "Isle of Man",
    "JE": "Jersey",
    "XK": "Kosovo",
}

EUROPE_COUNTRIES: dict[str, str] = {
    country.code: country.name
    for country in country_catalog().countries
    if country.continent == "Europe"
} | EUROPE_DIRECTORY_EXTRAS


def country_name(code: str) -> str:
    return EUROPE_COUNTRIES.get(code.upper(), code.upper())
