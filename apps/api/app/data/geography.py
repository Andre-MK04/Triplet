"""European flight geography: airport/metro codes -> city + country, and the
country/region vocabulary used to resolve destinations from natural language.

This is curated editorial reference data (not provider data), so it carries no
live-price honesty concerns. It covers the major scheduled airports plus the
IATA *city/metro* codes providers return (STO, PAR, ROM, MIL, MOW, LON, BER...),
because Travelpayouts mixes both namespaces.

Codes here define what counts as "European" for filtering and how any place name
a user types resolves to airport codes.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    code: str
    city: str
    country: str
    lat: float | None = None
    lon: float | None = None


# code -> Place. Airport codes and city/metro codes both included.
PLACES: dict[str, Place] = {
    # Austria
    "VIE": Place("VIE", "Vienna", "Austria", 48.11, 16.57),
    "GRZ": Place("GRZ", "Graz", "Austria", 46.99, 15.44),
    "SZG": Place("SZG", "Salzburg", "Austria", 47.79, 13.00),
    # Slovenia / Croatia
    "LJU": Place("LJU", "Ljubljana", "Slovenia", 46.22, 14.46),
    "ZAG": Place("ZAG", "Zagreb", "Croatia", 45.74, 16.07),
    "SPU": Place("SPU", "Split", "Croatia", 43.54, 16.30),
    "DBV": Place("DBV", "Dubrovnik", "Croatia", 42.56, 18.27),
    # Italy
    "VCE": Place("VCE", "Venice", "Italy", 45.51, 12.35),
    "TSF": Place("TSF", "Venice Treviso", "Italy", 45.65, 12.19),
    "TRS": Place("TRS", "Trieste", "Italy", 45.83, 13.47),
    "FCO": Place("FCO", "Rome Fiumicino", "Italy", 41.80, 12.24),
    "CIA": Place("CIA", "Rome Ciampino", "Italy", 41.80, 12.59),
    "ROM": Place("ROM", "Rome", "Italy", 41.90, 12.50),
    "MXP": Place("MXP", "Milan Malpensa", "Italy", 45.63, 8.72),
    "LIN": Place("LIN", "Milan Linate", "Italy", 45.45, 9.28),
    "BGY": Place("BGY", "Milan Bergamo", "Italy", 45.67, 9.70),
    "MIL": Place("MIL", "Milan", "Italy", 45.46, 9.19),
    "NAP": Place("NAP", "Naples", "Italy", 40.89, 14.29),
    "CTA": Place("CTA", "Catania", "Italy", 37.47, 15.07),
    "BLQ": Place("BLQ", "Bologna", "Italy", 44.53, 11.29),
    "PMO": Place("PMO", "Palermo", "Italy", 38.18, 13.10),
    # Spain
    "BCN": Place("BCN", "Barcelona", "Spain", 41.30, 2.08),
    "MAD": Place("MAD", "Madrid", "Spain", 40.47, -3.56),
    "VLC": Place("VLC", "Valencia", "Spain", 39.49, -0.48),
    "ALC": Place("ALC", "Alicante", "Spain", 38.28, -0.56),
    "AGP": Place("AGP", "Malaga", "Spain", 36.67, -4.50),
    "SVQ": Place("SVQ", "Seville", "Spain", 37.42, -5.90),
    "PMI": Place("PMI", "Palma de Mallorca", "Spain", 39.55, 2.74),
    "IBZ": Place("IBZ", "Ibiza", "Spain", 38.87, 1.37),
    "BIO": Place("BIO", "Bilbao", "Spain", 43.30, -2.91),
    # Portugal
    "LIS": Place("LIS", "Lisbon", "Portugal", 38.77, -9.13),
    "OPO": Place("OPO", "Porto", "Portugal", 41.24, -8.68),
    "FAO": Place("FAO", "Faro", "Portugal", 37.01, -7.97),
    # France
    "CDG": Place("CDG", "Paris CDG", "France", 49.01, 2.55),
    "ORY": Place("ORY", "Paris Orly", "France", 48.72, 2.38),
    "PAR": Place("PAR", "Paris", "France", 48.86, 2.35),
    "NCE": Place("NCE", "Nice", "France", 43.66, 7.22),
    "LYS": Place("LYS", "Lyon", "France", 45.73, 5.08),
    "MRS": Place("MRS", "Marseille", "France", 43.44, 5.22),
    "TLS": Place("TLS", "Toulouse", "France", 43.63, 1.37),
    "BOD": Place("BOD", "Bordeaux", "France", 44.83, -0.72),
    # Germany
    "BER": Place("BER", "Berlin", "Germany", 52.37, 13.50),
    "MUC": Place("MUC", "Munich", "Germany", 48.35, 11.79),
    "FRA": Place("FRA", "Frankfurt", "Germany", 50.03, 8.56),
    "DUS": Place("DUS", "Dusseldorf", "Germany", 51.29, 6.77),
    "HAM": Place("HAM", "Hamburg", "Germany", 53.63, 10.00),
    "CGN": Place("CGN", "Cologne", "Germany", 50.87, 7.14),
    "STR": Place("STR", "Stuttgart", "Germany", 48.69, 9.22),
    # Netherlands / Belgium / Luxembourg
    "AMS": Place("AMS", "Amsterdam", "Netherlands", 52.31, 4.76),
    "EIN": Place("EIN", "Eindhoven", "Netherlands", 51.45, 5.37),
    "BRU": Place("BRU", "Brussels", "Belgium", 50.90, 4.48),
    "CRL": Place("CRL", "Brussels Charleroi", "Belgium", 50.46, 4.45),
    "LUX": Place("LUX", "Luxembourg", "Luxembourg", 49.63, 6.21),
    # UK / Ireland
    "LON": Place("LON", "London", "United Kingdom", 51.51, -0.13),
    "LHR": Place("LHR", "London Heathrow", "United Kingdom", 51.47, -0.45),
    "LGW": Place("LGW", "London Gatwick", "United Kingdom", 51.15, -0.18),
    "STN": Place("STN", "London Stansted", "United Kingdom", 51.89, 0.24),
    "LTN": Place("LTN", "London Luton", "United Kingdom", 51.87, -0.37),
    "MAN": Place("MAN", "Manchester", "United Kingdom", 53.35, -2.27),
    "EDI": Place("EDI", "Edinburgh", "United Kingdom", 55.95, -3.37),
    "DUB": Place("DUB", "Dublin", "Ireland", 53.42, -6.27),
    # Nordics
    "CPH": Place("CPH", "Copenhagen", "Denmark", 55.62, 12.65),
    "BLL": Place("BLL", "Billund", "Denmark", 55.74, 9.15),
    "ARN": Place("ARN", "Stockholm Arlanda", "Sweden", 59.65, 17.93),
    "STO": Place("STO", "Stockholm", "Sweden", 59.33, 18.06),
    "GOT": Place("GOT", "Gothenburg", "Sweden", 57.66, 12.28),
    "OSL": Place("OSL", "Oslo", "Norway", 60.19, 11.10),
    "BGO": Place("BGO", "Bergen", "Norway", 60.29, 5.22),
    "TRD": Place("TRD", "Trondheim", "Norway", 63.46, 10.92),
    "HEL": Place("HEL", "Helsinki", "Finland", 60.32, 24.96),
    "KEF": Place("KEF", "Reykjavik", "Iceland", 63.99, -22.61),
    # Central / Eastern Europe
    "BUD": Place("BUD", "Budapest", "Hungary", 47.44, 19.26),
    "PRG": Place("PRG", "Prague", "Czechia", 50.10, 14.26),
    "WAW": Place("WAW", "Warsaw", "Poland", 52.17, 20.97),
    "KRK": Place("KRK", "Krakow", "Poland", 50.08, 19.80),
    "GDN": Place("GDN", "Gdansk", "Poland", 54.38, 18.47),
    "OTP": Place("OTP", "Bucharest", "Romania", 44.57, 26.10),
    "SOF": Place("SOF", "Sofia", "Bulgaria", 42.69, 23.41),
    "BTS": Place("BTS", "Bratislava", "Slovakia", 48.17, 17.21),
    "RIX": Place("RIX", "Riga", "Latvia", 56.92, 23.97),
    "TLL": Place("TLL", "Tallinn", "Estonia", 59.41, 24.83),
    "VNO": Place("VNO", "Vilnius", "Lithuania", 54.64, 25.28),
    # Greece / Cyprus / Malta
    "ATH": Place("ATH", "Athens", "Greece", 37.94, 23.94),
    "SKG": Place("SKG", "Thessaloniki", "Greece", 40.52, 22.97),
    "HER": Place("HER", "Heraklion", "Greece", 35.34, 25.18),
    "JMK": Place("JMK", "Mykonos", "Greece", 37.44, 25.35),
    "JTR": Place("JTR", "Santorini", "Greece", 36.40, 25.48),
    "LCA": Place("LCA", "Larnaca", "Cyprus", 34.88, 33.63),
    "MLA": Place("MLA", "Malta", "Malta", 35.86, 14.48),
    # Switzerland / Alps
    "ZRH": Place("ZRH", "Zurich", "Switzerland", 47.46, 8.55),
    "GVA": Place("GVA", "Geneva", "Switzerland", 46.24, 6.11),
    # Balkans
    "BEG": Place("BEG", "Belgrade", "Serbia", 44.82, 20.29),
    "TIA": Place("TIA", "Tirana", "Albania", 41.41, 19.72),
    "SKP": Place("SKP", "Skopje", "North Macedonia", 41.96, 21.62),
}

# Country -> representative airport codes (used to scope searches like "Sweden").
COUNTRY_TO_AIRPORTS: dict[str, list[str]] = {}
for _place in PLACES.values():
    COUNTRY_TO_AIRPORTS.setdefault(_place.country.lower(), []).append(_place.code)

# Region words -> the countries they cover.
REGION_TO_COUNTRIES: dict[str, list[str]] = {
    "scandinavia": ["Sweden", "Norway", "Denmark"],
    "nordics": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
    "iberia": ["Spain", "Portugal"],
    "benelux": ["Netherlands", "Belgium", "Luxembourg"],
    "baltics": ["Estonia", "Latvia", "Lithuania"],
    "balkans": ["Serbia", "Albania", "North Macedonia", "Croatia", "Bulgaria"],
    "british isles": ["United Kingdom", "Ireland"],
    "central europe": ["Austria", "Czechia", "Hungary", "Slovakia", "Poland", "Slovenia"],
    "mediterranean": ["Spain", "Italy", "Greece", "Portugal", "Croatia", "Malta", "Cyprus"],
}

# Common aliases so natural language resolves to a country key.
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
    "czechia": "Czechia",
}

EUROPEAN_COUNTRIES: set[str] = {place.country for place in PLACES.values()}


def is_european(code: str) -> bool:
    return code.upper() in PLACES


def estimate_duration_minutes(origin: str, destination: str) -> int | None:
    """Rough flight time from great-circle distance, when a provider omits it.

    Used so we don't discard the cheapest fare just because the feed lacked a
    duration field. Approximate by design (≈700 km/h cruise + 40 min overhead).
    """
    import math

    a = PLACES.get(origin.upper())
    b = PLACES.get(destination.upper())
    if not a or not b or a.lat is None or b.lat is None:
        return None
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    km = 2 * r * math.asin(min(1.0, math.sqrt(h)))
    return int(round(km / 700 * 60)) + 40


def place_country(code: str) -> str | None:
    place = PLACES.get(code.upper())
    return place.country if place else None


def place_city(code: str) -> str | None:
    place = PLACES.get(code.upper())
    return place.city if place else None


def airports_for_country(country: str) -> list[str]:
    key = COUNTRY_ALIASES.get(country.lower().strip(), country).lower()
    return list(COUNTRY_TO_AIRPORTS.get(key, []))


def airports_for_region(region: str) -> list[str]:
    codes: list[str] = []
    for country in REGION_TO_COUNTRIES.get(region.lower().strip(), []):
        codes.extend(COUNTRY_TO_AIRPORTS.get(country.lower(), []))
    return list(dict.fromkeys(codes))


# City names that are also common English words; only treat them as a place
# when a destination cue ("to Nice", "in Split") precedes them.
AMBIGUOUS_CITY_NAMES = {"nice", "split", "faro"}
_DESTINATION_CUE = r"(?:to|in|towards?|visit(?:ing)?|near)\s+(?:the\s+)?"


def resolve_place_names(text: str) -> list[str]:
    """Airport codes for any region, country, or city mentioned in free text.

    Regions expand to their countries' airports; countries to their airports;
    cities to their own code. Returns [] when nothing geographic is recognised.
    """
    lowered = f" {text.lower()} "
    codes: list[str] = []

    for region in REGION_TO_COUNTRIES:
        if f" {region} " in lowered or f" {region}." in lowered:
            codes.extend(airports_for_region(region))

    for alias, country in COUNTRY_ALIASES.items():
        if f" {alias} " in lowered:
            codes.extend(airports_for_country(country))
    for country in EUROPEAN_COUNTRIES:
        if f" {country.lower()} " in lowered:
            codes.extend(airports_for_country(country))

    # Cities: match on the city name; skip very short names to avoid false hits.
    for place in PLACES.values():
        city = place.city.lower()
        if len(city) < 4:
            continue
        if city in AMBIGUOUS_CITY_NAMES:
            if re.search(rf"\b{_DESTINATION_CUE}{re.escape(city)}\b", lowered):
                codes.append(place.code)
        elif f" {city} " in lowered:
            codes.append(place.code)

    return list(dict.fromkeys(codes))
