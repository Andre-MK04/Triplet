import re
from datetime import date

from app.data.country_catalog import country_catalog
from app.data.flight_places import REGION_TO_COUNTRY_CODES, get_place, is_supported_origin
from app.data.geography import resolve_place_names
from app.models import TripSearchRequest
from app.tools.schemas import ParsedTripIntent


# Origin-candidate cities Triplet flies users out of (the "from" side).
CITY_TO_AIRPORTS = {
    "ljubljana": ["LJU"],
    "zagreb": ["ZAG"],
    "vienna": ["VIE"],
    "graz": ["GRZ"],
    "budapest": ["BUD"],
    "trieste": ["TRS"],
    "venice": ["VCE", "TSF"],
}


def parse_trip_intent(message: str) -> ParsedTripIntent:
    text = message.lower()
    origin_airports = parse_origins(text)
    return_origin_airports = parse_return_origins(text, exclude=set(origin_airports))
    destination_countries, destination_regions, destination_continents = parse_destination_filters(
        text, origin_airports
    )
    has_broad_scope = bool(destination_countries or destination_regions or destination_continents)
    destination_airports = None if has_broad_scope else parse_destinations(
        text, exclude=set(origin_airports) | set(return_origin_airports or [])
    )
    route_stops = parse_route_stops(text, exclude=set(origin_airports))
    trip_plan = parse_trip_plan(text, return_origin_airports, route_stops)
    if trip_plan != "multi_city":
        route_stops = None
    exclude_europe = bool(re.search(r"\b(?:outside|beyond|not in) europe\b", text))
    unvisited_only = bool(
        re.search(r"\b(?:unvisited|somewhere new|never visited|haven't visited|have not visited)\b", text)
    )
    start_date, end_date = parse_date_range(text)
    min_days, max_days = parse_trip_length(text)
    max_budget = parse_budget(text)
    trip_style = parse_trip_style(text)
    direct_only = "direct only" in text or "direct flights" in text
    include_baggage = "with baggage" in text or "include baggage" in text or "baggage included" in text

    missing_fields: list[str] = []
    if not origin_airports:
        missing_fields.append("originAirports")
    if not start_date or not end_date:
        missing_fields.append("dateRange")
    if min_days is None or max_days is None:
        missing_fields.append("tripLength")
    if max_budget is None:
        missing_fields.append("maxBudget")
    if trip_style is None:
        trip_style = "surprise me"

    parsed_search = None
    if not missing_fields:
        parsed_search = TripSearchRequest(
            originAirports=origin_airports,
            destinationAirports=destination_airports,
            destinationCountries=destination_countries,
            destinationRegions=destination_regions,
            destinationContinents=destination_continents,
            excludeEurope=exclude_europe,
            unvisitedOnly=unvisited_only,
            returnOriginAirports=return_origin_airports,
            startDate=start_date,
            endDate=end_date,
            minTripLengthDays=min_days,
            maxTripLengthDays=max_days,
            maxBudget=max_budget,
            maxGroundTransferHours=4,
            tripStyle=trip_style,
            tripPlan=trip_plan,
            routeStops=route_stops,
            directOnly=direct_only,
            includeBaggage=include_baggage,
        )

    confidence = calculate_confidence(
        origin_airports=origin_airports,
        has_date_range=bool(start_date and end_date),
        has_trip_length=min_days is not None and max_days is not None,
        has_budget=max_budget is not None,
        has_trip_style=trip_style is not None,
    )

    return ParsedTripIntent(
        originAirports=origin_airports,
        destinationAirports=destination_airports,
        destinationCountries=destination_countries,
        destinationRegions=destination_regions,
        destinationContinents=destination_continents,
        excludeEurope=exclude_europe,
        unvisitedOnly=unvisited_only,
        returnOriginAirports=return_origin_airports,
        startDate=start_date,
        endDate=end_date,
        minTripLengthDays=min_days,
        maxTripLengthDays=max_days,
        maxBudget=max_budget,
        maxGroundTransferHours=4,
        tripStyle=trip_style,
        tripPlan=trip_plan,
        routeStops=route_stops,
        directOnly=direct_only,
        includeBaggage=include_baggage,
        parsedSearch=parsed_search,
        missingFields=missing_fields,
        confidence=confidence,
        notes="Rule-based placeholder parser. No LLM was called.",
    )


def parse_destinations(text: str, exclude: set[str] | None = None) -> list[str] | None:
    """Any explicit worldwide city or flight code named in the request.

    Origin airports are excluded so "from Vienna to Sweden" doesn't put Vienna
    on both sides. Returns None (= anywhere) when no place is recognised.
    """
    exclude = exclude or set()
    codes = [code for code in resolve_place_names(text) if code not in exclude]
    return codes or None


def parse_destination_filters(text: str, origin_airports: list[str]) -> tuple[list[str], list[str], list[str]]:
    padded = f" {text.casefold()} "
    origin_countries = {
        place.country_code for code in origin_airports if (place := get_place(code)) is not None
    }
    countries: list[str] = []
    for country in country_catalog().countries:
        names = (country.name, *country.aliases)
        if country.code not in origin_countries and any(f" {name.casefold()} " in padded for name in names):
            countries.append(country.code)
    regions = [region for region in REGION_TO_COUNTRY_CODES if f" {region} " in padded]
    continents = [
        continent
        for continent in country_catalog().continents
        if continent != "Antarctica"
        and f" {continent.casefold()} " in padded
        and not re.search(rf"\b(?:outside|beyond|not in) {re.escape(continent.casefold())}\b", text)
    ]
    return countries, regions, continents


_RETURN_FROM_PATTERN = re.compile(
    r"(?:then|and then|afterwards?|later)?\s*"
    r"(?:fly(?:ing)?\s+)?(?:back|home|return(?:ing)?)\s+from\s+([a-zà-ž .-]+?)(?=\s+(?:to|on|in|at|under|by|via)\b|[,.;!?]|$)"
    r"|then\s+from\s+([a-zà-ž .-]+?)(?=\s+(?:to|back|home)\b|[,.;!?]|$)",
    re.IGNORECASE,
)


def parse_return_origins(text: str, exclude: set[str] | None = None) -> list[str] | None:
    """Multi-city: the city the traveller flies home from, if they name one.

    Understands phrasings like "then from Helsinki to Budapest", "back from
    Helsinki" or "returning home from Helsinki". Returns None when the request
    is a plain out-and-back.
    """
    exclude = exclude or set()
    codes: list[str] = []
    for match in _RETURN_FROM_PATTERN.finditer(text):
        fragment = (match.group(1) or match.group(2) or "").strip()
        if not fragment:
            continue
        codes.extend(code for code in resolve_place_names(fragment) if code not in exclude)
    return list(dict.fromkeys(codes)) or None


# "from Munich", "leaving Porto or Lisbon", "departing from Kraków on the 5th".
# The city fragment is non-greedy so it stops at the first boundary word rather
# than swallowing the destination in "from Vienna to Lisbon".
_ORIGIN_FROM_PATTERN = re.compile(
    r"\b(?:from|out of|leaving|depart(?:ing)?(?:\s+from)?)\s+"
    r"([a-zà-ž][a-zà-ž.'-]*(?:\s+(?!(?:to|in|on|at|for|under|back|home)\b)[a-zà-ž][a-zà-ž.'-]*)*?)"
    r"(?=\s+(?:to|in|on|at|for|under|around|between|next|this|during|over|back|home)\b|[,.;!?]|$)",
    re.IGNORECASE,
)
# "flying back from Porto" and "then from Helsinki" name the city you fly HOME
# from, not where the trip starts.
_RETURN_CUE_BEFORE_FROM = re.compile(r"\b(?:back|home|return|returning|then|afterwards?|later)\s+$", re.IGNORECASE)


def parse_origins(text: str) -> list[str]:
    """European airports the traveller would fly out of.

    The curated city map covers the multi-airport home cities (Venice really is
    VCE and TSF), and anything else named after a "from"-style cue is resolved
    against the worldwide catalogue and kept only if it is in Europe — Triplet
    departs from Europe, so a non-European match is a misparse, not an origin.
    """
    airports: list[str] = []
    for city, codes in CITY_TO_AIRPORTS.items():
        if city in text:
            airports.extend(codes)

    for match in _ORIGIN_FROM_PATTERN.finditer(text):
        fragment = match.group(1).strip()
        if not fragment or _RETURN_CUE_BEFORE_FROM.search(text[: match.start()]):
            continue
        airports.extend(code for code in resolve_place_names(fragment, limit=4) if is_supported_origin(code))

    return list(dict.fromkeys(airports))


def parse_date_range(text: str) -> tuple[date | None, date | None]:
    if "july" in text:
        return date(2026, 7, 1), date(2026, 7, 31)
    if "august" in text:
        return date(2026, 8, 1), date(2026, 8, 31)
    return None, None


def parse_trip_length(text: str) -> tuple[int | None, int | None]:
    range_match = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)\s*(?:day|days|night|nights)", text)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    single_match = re.search(r"(\d+)\s*(?:day|days|night|nights)", text)
    if single_match:
        value = int(single_match.group(1))
        return value, value
    return None, None


# Units that mean the number is a length, a group size or a distance — anything
# but money. "for maximum 10 days" was being read as a EUR 10 budget, which then
# failed validation and sank the whole search.
_NOT_MONEY = r"(?!\s*(?:day|night|week|month|hour|hr|h\b|km|mile|people|person|pax|adult|passenger|stop|city|cities))"


def parse_budget(text: str) -> float | None:
    match = re.search(
        r"(?:under|below|max|maximum|budget|up to|no more than)\s*(?:of\s*)?"
        r"(?:€|eur|euros?|\$|usd)?\s*(\d+)\b" + _NOT_MONEY,
        text,
    )
    if not match:
        match = re.search(r"(\d+)\s*(?:€|eur|euros?)\b", text)
    return float(match.group(1)) if match else None


_MULTI_CITY_CUE = re.compile(
    r"\bmulti[- ]?city\b|\bcity hop\w*\b|\bthen\b|\bafter that\b|\bonwards? to\b",
    re.IGNORECASE,
)
_OPEN_JAW_CUE = re.compile(r"\bopen[- ]?jaw\b", re.IGNORECASE)
# "Rome then Athens then Istanbul" / "Rome, then Athens and then Istanbul".
_SEQUENCE_SPLIT = re.compile(r",|\bthen\b|\bafter that\b|\bonwards? to\b|\bnext\b", re.IGNORECASE)


def parse_trip_plan(
    text: str,
    return_origins: list[str] | None,
    route_stops: list[str] | None,
) -> str:
    """Which shape of trip the words describe.

    Return is the default and stays the default: someone who says "a week in
    Rome" wants a return trip, and guessing otherwise turns a simple request into
    an itinerary they did not ask for.
    """
    if _OPEN_JAW_CUE.search(text) or return_origins:
        return "open_jaw"
    if route_stops and len(route_stops) >= 2 and _MULTI_CITY_CUE.search(text):
        return "multi_city"
    return "return"


def parse_route_stops(text: str, exclude: set[str] | None = None) -> list[str] | None:
    """Cities to visit in the order they are named.

    Only a sequence counts. "Rome then Athens" is an itinerary; "Rome or Athens"
    is two candidates for one trip, and treating the second as a route would
    invent a journey nobody asked for.
    """
    exclude = exclude or set()
    if not _MULTI_CITY_CUE.search(text):
        return None
    stops: list[str] = []
    for fragment in _SEQUENCE_SPLIT.split(text):
        # One stop per fragment. A city name can match several places (Barcelona
        # is in Spain and in Venezuela), and a sequence names one city per step,
        # so the best match for the step is the only one that belongs in it.
        for code in resolve_place_names(fragment, limit=4):
            if code not in exclude and code not in stops:
                stops.append(code)
                break
    return stops[:6] if len(stops) >= 2 else None


def parse_trip_style(text: str) -> str | None:
    if "two cities" in text or "two-city" in text or "two nearby" in text:
        return "two nearby cities"
    if "one city" in text or "single city" in text:
        return "one city"
    if "surprise" in text:
        return "surprise me"
    return None


def calculate_confidence(
    origin_airports: list[str],
    has_date_range: bool,
    has_trip_length: bool,
    has_budget: bool,
    has_trip_style: bool,
) -> float:
    score = 0.2
    if origin_airports:
        score += 0.2
    if has_date_range:
        score += 0.2
    if has_trip_length:
        score += 0.2
    if has_budget:
        score += 0.15
    if has_trip_style:
        score += 0.05
    return min(score, 0.95)
