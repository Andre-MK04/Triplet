from datetime import datetime, time, timedelta

from app.config import settings
from app.data.flight_places import canonical_code, get_place, is_flightable_place, place_matches_filters
from app.data.geography import PLACES, distance_km, place_city, place_country_code, scope_matches
from app.models import Airport, DestinationMetadata, Flight, GroundTransfer, TripOption, TripSearchRequest
from app.pricing import build_price_info
from app.providers.travelpayouts.affiliate_links import ItinerarySegment, build_aviasales_itinerary_url
from app.providers.travelpayouts.mapper import RoundTripFare
from app.services.trip_explainer import build_explanation, build_tags, build_warnings
from app.services.trip_scoring import ScoringContext, calculate_deal_score, calculate_fit_score


def build_trips(
    request: TripSearchRequest,
    airports: list[Airport],
    flights: list[Flight],
    transfers: list[GroundTransfer],
    scoring: ScoringContext | None = None,
    enforce_budget: bool = True,
) -> list[TripOption]:
    airports_by_code = {airport.code: airport for airport in airports}
    origin_codes = {code.upper() for code in request.originAirports}
    destination_codes = (
        {canonical_code(code) for code in request.destinationAirports} if request.destinationAirports else None
    )
    # Multi-city: the traveller flies home from these airports, not the outbound city.
    return_origin_codes = (
        {canonical_code(code) for code in request.returnOriginAirports} if request.returnOriginAirports else None
    )
    outbound_candidates = [
        flight
        for flight in flights
        if flight.origin in origin_codes
        and (destination_codes is None or scope_matches(flight.destination, destination_codes))
        and place_matches_filters(
            flight.destination,
            country_codes={value.upper() for value in request.destinationCountries} or None,
            regions={value.casefold() for value in request.destinationRegions} or None,
            continents={value.casefold() for value in request.destinationContinents} or None,
            exclude_europe=request.excludeEurope,
        )
        and request.startDate <= flight.departureDateTime.date() <= request.endDate
        and destination_allowed_by_travel_map(flight.destination, request, scoring)
    ]

    trips: list[TripOption] = []

    for outbound in outbound_candidates:
        if outbound.destination not in airports_by_code:
            # Provider fares can reach any European airport; synthesize metadata
            # from geography so we don't drop them just for being unseeded.
            synthesized = synthesize_airport(outbound.destination)
            if not synthesized:
                continue
            airports_by_code[outbound.destination] = synthesized

        for return_flight in flights:
            if return_flight.origin not in airports_by_code:
                synthesized_return = synthesize_airport(return_flight.origin)
                if synthesized_return:
                    airports_by_code[return_flight.origin] = synthesized_return
            if not is_valid_return_candidate(outbound, return_flight, origin_codes, airports_by_code):
                continue
            if return_origin_codes is not None and not scope_matches(return_flight.origin, return_origin_codes):
                continue

            # Nights follow a simple travel-search convention: calendar days from
            # destination arrival date to return departure date.
            nights = (return_flight.departureDateTime.date() - outbound.arrivalDateTime.date()).days
            if nights <= 0:
                continue
            if nights < request.minTripLengthDays or nights > request.maxTripLengthDays:
                continue

            trip_type = classify_trip(outbound.destination, return_flight.origin, airports_by_code)
            if trip_type == "same_city" and request.tripStyle == "two nearby cities":
                continue
            # An explicit fly-home-from city overrides a "one city" style preference.
            if trip_type == "open_jaw" and request.tripStyle == "one city" and return_origin_codes is None:
                continue

            ground_transfer = None
            if trip_type == "open_jaw":
                ground_transfer = find_transfer(
                    outbound.destination,
                    return_flight.origin,
                    transfers,
                    airports_by_code,
                )
                if return_origin_codes is not None:
                    # The traveller explicitly asked for this city pair, so a
                    # missing/long transfer is estimated and flagged, not fatal.
                    if not ground_transfer:
                        ground_transfer = synthesize_transfer(outbound.destination, return_flight.origin)
                    if not ground_transfer:
                        continue
                else:
                    if not ground_transfer:
                        continue
                    if ground_transfer.durationHours > request.maxGroundTransferHours:
                        continue

            # Flights only. A ground crossing is estimated for planning, but
            # folding a train fare we never looked up into the trip total makes
            # the headline price disagree with everything it links to.
            total_price = round(outbound.price + return_flight.price, 2)
            over_budget = total_price > request.maxBudget
            if over_budget and enforce_budget:
                # "Anywhere" searches have plenty of in-budget options, so drop
                # the expensive ones. Specific-destination searches keep them
                # (flagged) so a requested place always yields something.
                continue

            warnings = build_warnings(
                outbound,
                return_flight,
                ground_transfer,
                nights,
                request.includeBaggage,
            )
            if over_budget:
                warnings.insert(0, f"Over your €{request.maxBudget:g} budget at €{total_price:g}.")
            if (
                return_origin_codes is not None
                and ground_transfer
                and ground_transfer.durationHours > request.maxGroundTransferHours
            ):
                warnings.append(
                    f"The {ground_transfer.fromCity} → {ground_transfer.toCity} leg is roughly "
                    f"{ground_transfer.durationHours:g}h by {ground_transfer.mode} — plan it as part of the trip "
                    f"(cost and time are estimates)."
                )
            if ground_transfer:
                transfer_km = distance_km(ground_transfer.fromAirport, ground_transfer.toAirport)
                crosses_border = place_country_code(ground_transfer.fromAirport) != place_country_code(
                    ground_transfer.toAirport
                )
                if crosses_border or (transfer_km is not None and transfer_km > 500):
                    warnings.append(
                        "This is a substantial self-transfer, not a protected flight connection; "
                        "verify border, visa, timing, and ground-transport details separately."
                    )
            itinerary_url = travelpayouts_itinerary_url(outbound, return_flight)
            itinerary_affiliate_url = itinerary_url if itinerary_url and settings.travelpayouts_marker else None
            trip = TripOption(
                id=f"{outbound.id}-{return_flight.id}",
                tripType=trip_type,
                outboundFlight=outbound,
                returnFlight=return_flight,
                groundTransfer=ground_transfer,
                totalPrice=total_price,
                tripLengthDays=nights,
                nights=nights,
                score=0,
                explanation="",
                warnings=warnings,
                tags=[],
                flightCost=round(outbound.price + return_flight.price, 2),
                groundEstimate=ground_transfer.estimatedCost if ground_transfer else None,
                # Two independently observed one-ways added together. Nobody
                # ever saw this itinerary priced as a whole, so it is an
                # estimate however real each half is.
                price=build_price_info(
                    amount=total_price,
                    kind=(
                        "estimated_open_jaw"
                        if trip_type == "open_jaw"
                        else "estimated_multi_city"
                    ),
                    observed_ats=[outbound.observedAt, return_flight.observedAt],
                    currency=outbound.currency,
                ),
                bookingUrl=itinerary_url or pick_trip_booking_url(outbound, return_flight),
                bookingLabel="Check price" if itinerary_url else pick_trip_booking_label(outbound, return_flight),
                affiliateUrl=itinerary_affiliate_url or pick_trip_affiliate_url(outbound, return_flight),
                providerDeepLink=itinerary_url or pick_trip_deep_link(outbound, return_flight),
                outboundBookingUrl=outbound.bookingUrl or outbound.deepLink,
                returnBookingUrl=return_flight.bookingUrl or return_flight.deepLink,
                provider=pick_trip_provider(outbound, return_flight),
                linkType=(
                    "affiliate_referral"
                    if itinerary_affiliate_url
                    else ("provider_deeplink" if itinerary_url else pick_trip_link_type(outbound, return_flight))
                ),
                destination=destination_metadata(outbound.destination),
            )
            trip.dealScore, trip.dealScoreBreakdown = calculate_deal_score(trip, request, scoring)
            trip.fitScore, trip.fitScoreBreakdown = calculate_fit_score(
                trip, request, scoring.profile if scoring else None, scoring
            )
            trip.score = trip.dealScore
            trip.explanation = build_explanation(trip, request, airports_by_code)
            trip.tags = build_tags(trip)
            trip.tags.extend(country_fit_tags(outbound.destination, scoring))
            if over_budget:
                trip.tags.insert(0, "Over budget")
            trips.append(trip)

    mark_relative_tags(trips)
    return sorted(
        trips,
        key=lambda trip: (
            -trip.dealScore,
            -(trip.fitScore or 0),
            trip.totalPrice,
            trip.groundTransfer.durationHours if trip.groundTransfer else 0,
        ),
    )[:30]


def is_valid_return_candidate(
    outbound: Flight,
    return_flight: Flight,
    origin_codes: set[str],
    airports_by_code: dict[str, Airport],
) -> bool:
    return (
        return_flight.destination in origin_codes
        and return_flight.origin in airports_by_code
        and return_flight.departureDateTime > outbound.arrivalDateTime
    )


def classify_trip(
    outbound_destination: str,
    return_origin: str,
    airports_by_code: dict[str, Airport],
) -> str:
    if outbound_destination == return_origin:
        return "same_city"
    if airport_area(outbound_destination, airports_by_code) == airport_area(return_origin, airports_by_code):
        return "same_city"
    return "open_jaw"


def airport_area(code: str, airports_by_code: dict[str, Airport]) -> str:
    airport = airports_by_code.get(code)
    if not airport:
        return code
    return airport.areaSlug or airport.city or code


def synthesize_transfer(from_airport: str, to_airport: str) -> GroundTransfer | None:
    """Rough between-cities journey for explicitly requested multi-city pairs.

    Estimated from great-circle distance (~80 km/h surface pace, ~€0.10/km) —
    honest ballparks the traveller must verify, never presented as bookable.
    """
    km = distance_km(from_airport, to_airport)
    if km is None:
        return None
    hours = round(km / 80 + 0.5, 1)
    cost = float(round(min(150.0, max(15.0, km * 0.10))))
    return GroundTransfer(
        fromAirport=from_airport.upper(),
        toAirport=to_airport.upper(),
        fromCity=place_city(from_airport) or from_airport.upper(),
        toCity=place_city(to_airport) or to_airport.upper(),
        durationHours=hours,
        estimatedCost=cost,
        mode="ground/self-transfer",
    )


def find_transfer(
    from_airport: str,
    to_airport: str,
    transfers: list[GroundTransfer],
    airports_by_code: dict[str, Airport],
) -> GroundTransfer | None:
    from_area = airport_area(from_airport, airports_by_code)
    to_area = airport_area(to_airport, airports_by_code)
    for transfer in transfers:
        exact_airport_match = transfer.fromAirport == from_airport and transfer.toAirport == to_airport
        area_match = (
            airport_area(transfer.fromAirport, airports_by_code) == from_area
            and airport_area(transfer.toAirport, airports_by_code) == to_area
        )
        if exact_airport_match or area_match:
            return transfer
    return None


def mark_relative_tags(trips: list[TripOption]) -> None:
    if not trips:
        return

    cheapest = min(trips, key=lambda trip: trip.totalPrice)
    best_score = max(trips, key=lambda trip: trip.score)
    if "Cheapest" not in cheapest.tags:
        cheapest.tags.insert(0, "Cheapest")
    if "Best score" not in best_score.tags:
        best_score.tags.insert(0, "Best score")


# Providers whose links point at an external search/booking page.
LINKABLE_PROVIDERS = {"skyscanner", "travelpayouts"}


def pick_trip_provider(outbound: Flight, return_flight: Flight) -> str | None:
    if outbound.provider == return_flight.provider:
        return outbound.provider
    for provider in (outbound.provider, return_flight.provider):
        if provider in LINKABLE_PROVIDERS:
            return provider
    return outbound.provider or return_flight.provider


def pick_trip_deep_link(outbound: Flight, return_flight: Flight) -> str | None:
    if outbound.deepLink:
        return outbound.deepLink
    if return_flight.deepLink:
        return return_flight.deepLink
    for flight in (outbound, return_flight):
        if flight.provider in LINKABLE_PROVIDERS and flight.bookingUrl:
            return flight.bookingUrl
    return None


def pick_trip_affiliate_url(outbound: Flight, return_flight: Flight) -> str | None:
    for flight in (outbound, return_flight):
        if flight.affiliateUrl:
            return flight.affiliateUrl
    for flight in (outbound, return_flight):
        if flight.provider in LINKABLE_PROVIDERS and flight.bookingUrl and not flight.deepLink:
            return flight.bookingUrl
    return None


def pick_trip_booking_url(outbound: Flight, return_flight: Flight) -> str | None:
    return pick_trip_deep_link(outbound, return_flight) or pick_trip_affiliate_url(outbound, return_flight)


def pick_trip_link_type(outbound: Flight, return_flight: Flight) -> str:
    if pick_trip_deep_link(outbound, return_flight):
        return "provider_deeplink"
    if pick_trip_affiliate_url(outbound, return_flight):
        return "affiliate_referral"
    return "none"


def pick_trip_booking_label(outbound: Flight, return_flight: Flight) -> str | None:
    link_type = pick_trip_link_type(outbound, return_flight)
    if link_type == "provider_deeplink":
        return "View deal"
    if link_type == "affiliate_referral":
        return "Check price"
    return None


def travelpayouts_itinerary_url(outbound: Flight, return_flight: Flight) -> str | None:
    if outbound.provider != "travelpayouts" and return_flight.provider != "travelpayouts":
        return None
    return build_aviasales_itinerary_url(
        [
            ItinerarySegment(outbound.origin, outbound.destination, outbound.departureDateTime),
            ItinerarySegment(return_flight.origin, return_flight.destination, return_flight.departureDateTime),
        ]
    )


def destination_metadata(code: str) -> DestinationMetadata | None:
    place = get_place(code)
    if not place:
        return None
    return DestinationMetadata(
        code=place.code,
        kind=place.kind,
        city=place_city(place.code) or place.name,
        country=place.country_name,
        countryCode=place.country_code,
        continent=place.continent,
    )


def synthesize_airport(code: str) -> Airport | None:
    """Build airport metadata for a provider code from the geography dataset.

    Returns None only when the code is absent from the flightable global catalogue.
    """
    place = PLACES.get(code.upper())
    if not place:
        return None
    return Airport(
        code=place.code,
        name=place.city,
        city=place.city,
        country=place.country,
        latitude=place.lat,
        longitude=place.lon,
        areaSlug=place.city.lower().replace(" ", "-"),
        areaName=place.city,
    )


def build_round_trip_options(
    fares: list[RoundTripFare],
    request: TripSearchRequest,
    scoring: ScoringContext | None = None,
    enforce_budget: bool = True,
) -> list[TripOption]:
    """Turn city-directions round-trip fares into scored same-city trips.

    These are complete round-trip bundles (one price, real dates), so there is no
    one-way pairing and the total is the true round-trip fare, not a sum. Fares are
    kept only when globally flightable, within budget, in the requested date
    window, and within any requested geographic scope.
    """
    destination_codes = (
        {canonical_code(code) for code in request.destinationAirports} if request.destinationAirports else None
    )
    origin_codes = {code.upper() for code in request.originAirports}
    # Round-trip fares carry no per-leg one-way price, so route history (one-way
    # baselines) must not be applied; keep only the profile for fit scoring.
    bundle_scoring = ScoringContext(
        profile=scoring.profile if scoring else None,
        country_states=scoring.country_states if scoring else {},
    )

    trips: list[TripOption] = []
    for fare in fares:
        destination = canonical_code(fare.destination)
        if destination in origin_codes or not is_flightable_place(destination):
            continue
        if destination_codes is not None and not scope_matches(destination, destination_codes):
            continue
        if not place_matches_filters(
            destination,
            country_codes={value.upper() for value in request.destinationCountries} or None,
            regions={value.casefold() for value in request.destinationRegions} or None,
            continents={value.casefold() for value in request.destinationContinents} or None,
            exclude_europe=request.excludeEurope,
        ):
            continue
        if request.directOnly and (fare.stops or 0) > 0:
            continue
        if not destination_allowed_by_travel_map(destination, request, scoring):
            continue
        over_budget = fare.price > request.maxBudget
        if over_budget and enforce_budget:
            continue
        departure = parse_iso_date(fare.departureDate)
        return_date = parse_iso_date(fare.returnDate)
        if not departure or not (request.startDate <= departure <= request.endDate):
            continue
        nights = (return_date - departure).days if return_date else request.minTripLengthDays
        if nights <= 0:
            nights = request.minTripLengthDays
        if nights < request.minTripLengthDays or nights > request.maxTripLengthDays:
            continue

        duration = estimate_bundle_duration_minutes(fare.origin, destination)
        outbound_departure = datetime.combine(departure, time(hour=9))
        return_departure = datetime.combine(return_date or departure, time(hour=18))
        search_url = build_aviasales_itinerary_url(
            [
                ItinerarySegment(fare.origin, destination, departure),
                ItinerarySegment(destination, fare.origin, return_date or departure),
            ]
        )
        # The provider's own link identifies the exact fare we are quoting, so the
        # page the traveller lands on shows this trip rather than a fresh search
        # that may surface a different itinerary at a different price. Our
        # constructed route+dates search is the fallback when there is no link.
        itinerary_url = fare.bookingUrl or search_url
        itinerary_affiliate_url = (
            fare.affiliateUrl
            or (search_url if search_url and settings.travelpayouts_marker else None)
        )

        outbound = Flight(
            id=f"rt-out-{fare.origin}-{destination}-{departure.isoformat()}",
            origin=fare.origin.upper(),
            destination=destination,
            departureDateTime=outbound_departure,
            arrivalDateTime=outbound_departure + timedelta(minutes=duration),
            airline=fare.airline or "Multiple airlines",
            price=fare.price,
            currency=fare.currency,
            bookingUrl=itinerary_url,
            deepLink=itinerary_url,
            affiliateUrl=itinerary_affiliate_url,
            provider="travelpayouts",
            stops=fare.stops,
            durationMinutes=duration,
            isLive=False,
            confidenceLevel="indicative",
            observedAt=fare.observedAt,
            expiresAt=fare.expiresAt,
        )
        inbound = Flight(
            id=f"rt-ret-{destination}-{fare.origin}-{(return_date or departure).isoformat()}",
            origin=destination,
            destination=fare.origin.upper(),
            departureDateTime=return_departure,
            arrivalDateTime=return_departure + timedelta(minutes=duration),
            airline=fare.airline or "Multiple airlines",
            price=0.0,  # part of the round-trip bundle; total is on the trip
            currency=fare.currency,
            bookingUrl=itinerary_url,
            deepLink=itinerary_url,
            affiliateUrl=itinerary_affiliate_url,
            provider="travelpayouts",
            stops=fare.stops,
            durationMinutes=duration,
            isLive=False,
            confidenceLevel="indicative",
            observedAt=fare.observedAt,
            expiresAt=fare.expiresAt,
        )
        trip = TripOption(
            id=f"rt-{fare.origin}-{destination}-{departure.isoformat()}",
            tripType="same_city",
            outboundFlight=outbound,
            returnFlight=inbound,
            groundTransfer=None,
            totalPrice=round(fare.price, 2),
            tripLengthDays=nights,
            nights=nights,
            score=0,
            fareKind="round_trip_bundle",
            flightCost=round(fare.price, 2),
            # One provider observation of this exact round trip — the strongest
            # thing we can show, because it is what Aviasales itself recorded.
            price=build_price_info(
                amount=fare.price,
                kind="cached_return",
                observed_ats=[fare.observedAt],
                currency=fare.currency,
            ),
            explanation="",
            warnings=["Round-trip fare; confirm exact times and baggage on the provider site."],
            tags=["Round trip"],
            bookingUrl=itinerary_url or fare.bookingUrl,
            bookingLabel="Check price" if itinerary_url or fare.bookingUrl else None,
            affiliateUrl=itinerary_affiliate_url or fare.affiliateUrl,
            providerDeepLink=itinerary_url or fare.bookingUrl,
            provider="travelpayouts",
            linkType=(
                "affiliate_referral"
                if itinerary_affiliate_url or fare.affiliateUrl
                else ("provider_deeplink" if itinerary_url or fare.bookingUrl else "none")
            ),
            destination=destination_metadata(destination),
        )
        trip.dealScore, trip.dealScoreBreakdown = calculate_deal_score(trip, request, bundle_scoring)
        trip.fitScore, trip.fitScoreBreakdown = calculate_fit_score(
            trip, request, bundle_scoring.profile, bundle_scoring
        )
        trip.score = trip.dealScore
        city = place_city(destination) or destination
        trip.explanation = (
            f"A round trip from {place_city(fare.origin) or fare.origin} to {city} for "
            f"{fare.currency} {round(fare.price)} total — the cheapest we found to {city} in your window."
        )
        trip.tags.extend(build_tags(trip))
        trip.tags.extend(country_fit_tags(destination, scoring))
        if over_budget:
            trip.tags.insert(0, "Over budget")
            trip.warnings.insert(0, f"Over your €{request.maxBudget:g} budget at €{round(fare.price):g}.")
        trips.append(trip)

    mark_relative_tags(trips)
    return sorted(trips, key=lambda t: (-t.dealScore, -(t.fitScore or 0), t.totalPrice))


def estimate_bundle_duration_minutes(origin: str, destination: str) -> int:
    from app.data.geography import estimate_duration_minutes

    return estimate_duration_minutes(origin, destination) or 180


def destination_allowed_by_travel_map(
    destination: str,
    request: TripSearchRequest,
    scoring: ScoringContext | None,
) -> bool:
    if not request.unvisitedOnly or not scoring or not scoring.country_states:
        return True
    place = get_place(destination)
    return bool(place and scoring.country_states.get(place.country_code) not in {"visited", "lived"})


def country_fit_tags(destination: str, scoring: ScoringContext | None) -> list[str]:
    if not scoring or not scoring.country_states:
        return []
    place = get_place(destination)
    if not place:
        return []
    state = scoring.country_states.get(place.country_code)
    if state == "wishlist":
        return ["Wishlist"]
    if state is None:
        return ["New country"]
    return []


def parse_iso_date(value: str | None):
    from datetime import date as _date

    if not value:
        return None
    try:
        return _date.fromisoformat(value[:10])
    except ValueError:
        return None


def merge_trip_options(
    paired: list[TripOption],
    bundles: list[TripOption],
    per_destination_limit: int = 1,
) -> list[TripOption]:
    """Combine one-way-paired trips with round-trip bundles.

    Identical departures for the same route collapse to the cheaper option (a
    round-trip bundle usually beats two summed one-ways). Beyond that,
    ``per_destination_limit`` decides how many dated options a destination may
    contribute: an "anywhere" search wants one per place so the results show
    variety, while a search that named a place wants a few dates to choose
    between. Re-ranks by deal score, then fit, then price, and caps the result.
    """
    by_departure: dict[tuple[str, str, object], TripOption] = {}
    order: list[tuple[str, str, object]] = []
    for trip in paired + bundles:
        key = (
            trip.outboundFlight.origin,
            trip.outboundFlight.destination,
            trip.outboundFlight.departureDateTime.date(),
        )
        existing = by_departure.get(key)
        if existing is None:
            by_departure[key] = trip
            order.append(key)
        elif trip.totalPrice < existing.totalPrice:
            by_departure[key] = trip

    ranked = sorted(
        (by_departure[key] for key in order),
        key=lambda trip: (
            -trip.dealScore,
            -(trip.fitScore or 0),
            trip.totalPrice,
        ),
    )

    seen_per_destination: dict[tuple[str, str], int] = {}
    merged: list[TripOption] = []
    for trip in ranked:
        route = (trip.outboundFlight.origin, trip.outboundFlight.destination)
        count = seen_per_destination.get(route, 0)
        if count >= max(1, per_destination_limit):
            continue
        seen_per_destination[route] = count + 1
        merged.append(trip)
        if len(merged) >= 30:
            break

    mark_relative_tags(merged)
    return merged
