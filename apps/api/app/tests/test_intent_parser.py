from datetime import date

from app.ai.intent_parser import parse_trip_intent


def test_parses_from_vienna_or_zagreb():
    intent = parse_trip_intent("Find trips from Vienna or Zagreb in August under 180 euros for 5 to 7 days.")

    assert intent.originAirports == ["ZAG", "VIE"] or intent.originAirports == ["VIE", "ZAG"]


def test_parses_under_180_euros():
    intent = parse_trip_intent("from Vienna in August under 180 euros for 5 to 7 days")

    assert intent.maxBudget == 180


def test_parses_5_to_7_days():
    intent = parse_trip_intent("from Vienna in August under 180 euros for 5 to 7 days")

    assert intent.minTripLengthDays == 5
    assert intent.maxTripLengthDays == 7


def test_parses_july_date_range():
    intent = parse_trip_intent("from Vienna in July under 180 euros for 5 days")

    assert intent.startDate == date(2026, 7, 1)
    assert intent.endDate == date(2026, 7, 31)


def test_parses_august_date_range():
    intent = parse_trip_intent("from Vienna in August under 180 euros for 5 days")

    assert intent.startDate == date(2026, 8, 1)
    assert intent.endDate == date(2026, 8, 31)


def test_parses_two_cities_trip_style():
    intent = parse_trip_intent("from Vienna in August under 180 euros for 5 days, I like two cities")

    assert intent.tripStyle == "two nearby cities"


def test_returns_missing_date_range_when_no_month_found():
    intent = parse_trip_intent("from Vienna under 180 euros for 5 days")

    assert "dateRange" in intent.missingFields


def test_maps_venice_to_vce_and_tsf():
    intent = parse_trip_intent("from Venice in August under 180 euros for 5 days")

    assert intent.originAirports == ["VCE", "TSF"]


def test_parses_scandinavia_region_as_destination():
    intent = parse_trip_intent(
        "from Vienna in August under 300 euros for 5 days, trip to Scandinavia"
    )

    assert intent.originAirports == ["VIE"]
    assert intent.destinationAirports is not None
    # Scandinavia = Sweden + Norway + Denmark airports; all Nordic, no origin leak.
    assert {"ARN", "GOT", "OSL", "BGO", "CPH"} <= set(intent.destinationAirports)
    assert "VIE" not in intent.destinationAirports
    assert "BCN" not in intent.destinationAirports


def test_parses_country_name_as_destination():
    intent = parse_trip_intent("find me trips to Sweden in July from Vienna")

    assert intent.originAirports == ["VIE"]
    assert set(intent.destinationAirports) == {"ARN", "STO", "GOT"}


def test_parses_named_destination_city():
    intent = parse_trip_intent(
        "from Vienna in August under 300 euros for 5 days to Copenhagen"
    )

    assert intent.destinationAirports == ["CPH"]
    assert intent.originAirports == ["VIE"]


def test_no_destination_stays_anywhere():
    intent = parse_trip_intent("from Vienna in August under 200 euros for 5 days")

    assert intent.destinationAirports is None
