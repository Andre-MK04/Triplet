import re
from datetime import date

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
    destination_airports = parse_destinations(
        text, exclude=set(origin_airports) | set(return_origin_airports or [])
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
            returnOriginAirports=return_origin_airports,
            startDate=start_date,
            endDate=end_date,
            minTripLengthDays=min_days,
            maxTripLengthDays=max_days,
            maxBudget=max_budget,
            maxGroundTransferHours=4,
            tripStyle=trip_style,
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
        returnOriginAirports=return_origin_airports,
        startDate=start_date,
        endDate=end_date,
        minTripLengthDays=min_days,
        maxTripLengthDays=max_days,
        maxBudget=max_budget,
        maxGroundTransferHours=4,
        tripStyle=trip_style,
        directOnly=direct_only,
        includeBaggage=include_baggage,
        parsedSearch=parsed_search,
        missingFields=missing_fields,
        confidence=confidence,
        notes="Rule-based placeholder parser. No LLM was called.",
    )


def parse_destinations(text: str, exclude: set[str] | None = None) -> list[str] | None:
    """Any European region, country, or city named in the request.

    Origin airports are excluded so "from Vienna to Sweden" doesn't put Vienna
    on both sides. Returns None (= anywhere) when no place is recognised.
    """
    exclude = exclude or set()
    codes = [code for code in resolve_place_names(text) if code not in exclude]
    return codes or None


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


def parse_origins(text: str) -> list[str]:
    airports: list[str] = []
    for city, codes in CITY_TO_AIRPORTS.items():
        if city in text:
            airports.extend(codes)
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


def parse_budget(text: str) -> float | None:
    match = re.search(r"(?:under|below|max|maximum|budget)\s*(?:€|eur|euros?)?\s*(\d+)", text)
    if not match:
        match = re.search(r"(\d+)\s*(?:€|eur|euros?)", text)
    return float(match.group(1)) if match else None


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
