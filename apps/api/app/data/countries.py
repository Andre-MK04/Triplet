"""ISO 3166-1 alpha-2 codes for the European coverage area.

Used by the GeoNames/OurAirports import scripts to scope seeding to Europe and
to resolve country names without an extra dataset. Expanding worldwide later
means widening (or dropping) this filter — nothing else assumes Europe.
"""

EUROPE_COUNTRIES: dict[str, str] = {
    "AD": "Andorra",
    "AL": "Albania",
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BY": "Belarus",
    "CH": "Switzerland",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FO": "Faroe Islands",
    "FR": "France",
    "GB": "United Kingdom",
    "GG": "Guernsey",
    "GI": "Gibraltar",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IM": "Isle of Man",
    "IS": "Iceland",
    "IT": "Italy",
    "JE": "Jersey",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "MT": "Malta",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SM": "San Marino",
    "UA": "Ukraine",
    "XK": "Kosovo",
}


def country_name(code: str) -> str:
    return EUROPE_COUNTRIES.get(code.upper(), code.upper())
