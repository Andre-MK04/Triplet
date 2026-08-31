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
    assert intent.destinationAirports is None
    assert intent.destinationRegions == ["scandinavia"]


def test_parses_country_name_as_destination():
    intent = parse_trip_intent("find me trips to Sweden in July from Vienna")

    assert intent.originAirports == ["VIE"]
    assert intent.destinationAirports is None
    assert intent.destinationCountries == ["SE"]


def test_parses_named_destination_city():
    intent = parse_trip_intent(
        "from Vienna in August under 300 euros for 5 days to Copenhagen"
    )

    assert intent.destinationAirports == ["CPH"]
    assert intent.originAirports == ["VIE"]


def test_no_destination_stays_anywhere():
    intent = parse_trip_intent("from Vienna in August under 200 euros for 5 days")

    assert intent.destinationAirports is None


def test_parses_multi_city_then_from_phrasing():
    intent = parse_trip_intent(
        "i want to go from budapest to stockholm and then from helsinki back to budapest in august for 7 days under 300"
    )

    assert intent.originAirports == ["BUD"]
    assert intent.destinationAirports == ["STO"]
    assert intent.returnOriginAirports == ["HEL"]


def test_parses_multi_city_flying_back_from_phrasing():
    intent = parse_trip_intent("from vienna to lisbon in august, 5 days under 200, flying back from porto")

    assert intent.originAirports == ["VIE"]
    assert intent.destinationAirports == ["LIS"]
    assert intent.returnOriginAirports == ["OPO"]


def test_plain_round_trip_has_no_return_origin():
    intent = parse_trip_intent("from vienna to copenhagen in august for 5 days under 200")

    assert intent.returnOriginAirports is None


def test_parses_worldwide_geographic_and_travel_map_filters():
    intent = parse_trip_intent(
        "from Vienna somewhere new outside Europe in August for 8 days under 900"
    )

    assert intent.destinationAirports is None
    assert intent.excludeEurope is True
    assert intent.unvisitedOnly is True
    assert intent.destinationContinents == []


def test_a_plain_request_stays_a_return_trip():
    """The default must hold: naming one place is not asking for an itinerary."""
    for message in (
        "a week in rome from vienna in august under 300",
        "from vienna to rome or athens in august, 5 days under 300",
        "somewhere warm from vienna in august for 7 days under 400",
    ):
        intent = parse_trip_intent(message)
        assert intent.tripPlan == "return", message
        assert intent.routeStops is None


def test_a_named_sequence_of_cities_is_a_multi_city_trip():
    intent = parse_trip_intent(
        "from vienna to rome then athens then istanbul in august for 9-12 days under 400"
    )

    assert intent.tripPlan == "multi_city"
    assert intent.routeStops == ["ROM", "ATH", "IST"]


def test_multi_city_takes_one_stop_per_step_despite_duplicate_city_names():
    # Barcelona is a city in Spain and another in Venezuela; a step names one.
    intent = parse_trip_intent(
        "a multi city trip from budapest to barcelona then lisbon in august, 8-12 days under 500"
    )

    assert intent.routeStops == ["BCN", "LIS"]


def test_flying_home_from_another_city_is_an_open_jaw_not_a_multi_city():
    intent = parse_trip_intent(
        "from budapest to stockholm, then from helsinki back to budapest in august 5 days under 300"
    )

    assert intent.tripPlan == "open_jaw"
    assert intent.returnOriginAirports == ["HEL"]
    assert intent.routeStops is None


def test_the_phrase_open_jaw_is_understood_directly():
    intent = parse_trip_intent(
        "an open jaw trip from vienna to barcelona home from lisbon in august 6 days under 300"
    )

    assert intent.tripPlan == "open_jaw"
    assert intent.returnOriginAirports == ["LIS"]


def test_a_length_is_not_read_as_a_budget():
    """"maximum 10 days" was parsed as a EUR 10 budget, which failed validation
    and returned no trips at all for the whole search."""
    intent = parse_trip_intent(
        "find me a fun trip to scandinavia for maximum 10 days in september or october"
    )

    assert intent.maxBudget is None
    assert (intent.minTripLengthDays, intent.maxTripLengthDays) == (10, 10)
    assert intent.destinationRegions == ["scandinavia"]


def test_real_budgets_still_parse():
    from app.ai.intent_parser import parse_budget

    assert parse_budget("a trip under 400 euros for 5 days") == 400
    assert parse_budget("max 300 for a week") == 300
    assert parse_budget("budget of 250") == 250
    assert parse_budget("up to 700 eur, 8-12 days") == 700
    assert parse_budget("8-12 days under €900") == 900
    # Counts of people are not money either.
    assert parse_budget("max 3 people under 450") == 450


def test_other_units_are_not_budgets():
    from app.ai.intent_parser import parse_budget

    assert parse_budget("no more than 5 nights") is None
    assert parse_budget("maximum 2 weeks") is None
    assert parse_budget("under 3 hours of ground transfer") is None
