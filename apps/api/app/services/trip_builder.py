from datetime import datetime, time

from app.data.geography import PLACES, is_european, place_city
from app.models import Airport, Flight, GroundTransfer, TripOption, TripSearchRequest
from app.providers.travelpayouts.mapper import RoundTripFare
from app.services.trip_explainer import build_explanation, build_tags, build_warnings
from app.services.trip_scoring import ScoringContext, calculate_deal_score, calculate_fit_score


def build_trips(
    request: TripSearchRequest,
    airports: list[Airport],
    flights: list[Flight],
    transfers: list[GroundTransfer],
    scoring: ScoringContext | None = None,
) -> list[TripOption]:
    airports_by_code = {airport.code: airport for airport in airports}
    origin_codes = {code.upper() for code in request.originAirports}
    destination_codes = (
        {code.upper() for code in request.destinationAirports} if request.destinationAirports else None
    )
    outbound_candidates = [
        flight
        for flight in flights
        if flight.origin in origin_codes
        and (destination_codes is None or flight.destination in destination_codes)
        and request.startDate <= flight.departureDateTime.date() <= request.endDate
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
            if not is_valid_return_candidate(outbound, return_flight, origin_codes, airports_by_code):
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
            if trip_type == "open_jaw" and request.tripStyle == "one city":
                continue

            ground_transfer = None
            if trip_type == "open_jaw":
                ground_transfer = find_transfer(
                    outbound.destination,
                    return_flight.origin,
                    transfers,
                    airports_by_code,
                )
                if not ground_transfer:
                    continue
                if ground_transfer.durationHours > request.maxGroundTransferHours:
                    continue

            total_price = round(
                outbound.price
                + return_flight.price
                + (ground_transfer.estimatedCost if ground_transfer else 0),
                2,
            )
            if total_price > request.maxBudget:
                continue

            warnings = build_warnings(
                outbound,
                return_flight,
                ground_transfer,
                nights,
                request.includeBaggage,
            )
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
                bookingUrl=pick_trip_booking_url(outbound, return_flight),
                bookingLabel=pick_trip_booking_label(outbound, return_flight),
                affiliateUrl=pick_trip_affiliate_url(outbound, return_flight),
                providerDeepLink=pick_trip_deep_link(outbound, return_flight),
                outboundBookingUrl=outbound.bookingUrl or outbound.deepLink,
                returnBookingUrl=return_flight.bookingUrl or return_flight.deepLink,
                provider=pick_trip_provider(outbound, return_flight),
                linkType=pick_trip_link_type(outbound, return_flight),
            )
            trip.dealScore, trip.dealScoreBreakdown = calculate_deal_score(trip, request, scoring)
            trip.fitScore, trip.fitScoreBreakdown = calculate_fit_score(
                trip, request, scoring.profile if scoring else None
            )
            trip.score = trip.dealScore
            trip.explanation = build_explanation(trip, request, airports_by_code)
            trip.tags = build_tags(trip)
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
LINKABLE_PROVIDERS = {"skyscanner", "duffel", "travelpayouts"}


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


def synthesize_airport(code: str) -> Airport | None:
    """Build airport metadata for a provider code from the geography dataset.

    Returns None only when the code is not a known European place, so unknown
    non-European codes are still excluded.
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
) -> list[TripOption]:
    """Turn city-directions round-trip fares into scored same-city trips.

    These are complete round-trip bundles (one price, real dates), so there is no
    one-way pairing and the total is the true round-trip fare, not a sum. Fares are
    kept only when European, within budget, in the requested date window, and — if
    the request scopes destinations — within that scope.
    """
    destination_codes = (
        {code.upper() for code in request.destinationAirports} if request.destinationAirports else None
    )
    origin_codes = {code.upper() for code in request.originAirports}
    # Round-trip fares carry no per-leg one-way price, so route history (one-way
    # baselines) must not be applied; keep only the profile for fit scoring.
    bundle_scoring = ScoringContext(profile=scoring.profile if scoring else None)

    trips: list[TripOption] = []
    for fare in fares:
        destination = fare.destination.upper()
        if destination in origin_codes or not is_european(destination):
            continue
        if destination_codes is not None and destination not in destination_codes:
            continue
        if fare.price > request.maxBudget:
            continue
        departure = parse_iso_date(fare.departureDate)
        return_date = parse_iso_date(fare.returnDate)
        if not departure or not (request.startDate <= departure <= request.endDate):
            continue
        nights = (return_date - departure).days if return_date else request.minTripLengthDays
        if nights <= 0:
            nights = request.minTripLengthDays

        outbound = Flight(
            id=f"rt-out-{fare.origin}-{destination}-{departure.isoformat()}",
            origin=fare.origin.upper(),
            destination=destination,
            departureDateTime=datetime.combine(departure, time(hour=9)),
            arrivalDateTime=datetime.combine(departure, time(hour=12)),
            airline=fare.airline or "Multiple airlines",
            price=fare.price,
            currency=fare.currency,
            bookingUrl=fare.bookingUrl,
            deepLink=fare.bookingUrl,
            affiliateUrl=fare.affiliateUrl,
            provider="travelpayouts",
            stops=fare.stops,
            isLive=False,
            confidenceLevel="indicative",
        )
        inbound = Flight(
            id=f"rt-ret-{destination}-{fare.origin}-{(return_date or departure).isoformat()}",
            origin=destination,
            destination=fare.origin.upper(),
            departureDateTime=datetime.combine(return_date or departure, time(hour=18)),
            arrivalDateTime=datetime.combine(return_date or departure, time(hour=21)),
            airline=fare.airline or "Multiple airlines",
            price=0.0,  # part of the round-trip bundle; total is on the trip
            currency=fare.currency,
            bookingUrl=fare.bookingUrl,
            deepLink=fare.bookingUrl,
            affiliateUrl=fare.affiliateUrl,
            provider="travelpayouts",
            stops=fare.stops,
            isLive=False,
            confidenceLevel="indicative",
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
            explanation="",
            warnings=["Round-trip fare; confirm exact times and baggage on the provider site."],
            tags=["Round trip"],
            bookingUrl=fare.bookingUrl,
            bookingLabel="Check price" if fare.bookingUrl else None,
            affiliateUrl=fare.affiliateUrl,
            providerDeepLink=fare.bookingUrl,
            provider="travelpayouts",
            linkType="affiliate_referral" if fare.affiliateUrl else ("provider_deeplink" if fare.bookingUrl else "none"),
        )
        trip.dealScore, trip.dealScoreBreakdown = calculate_deal_score(trip, request, bundle_scoring)
        trip.fitScore, trip.fitScoreBreakdown = calculate_fit_score(trip, request, bundle_scoring.profile)
        trip.score = trip.dealScore
        city = place_city(destination) or destination
        trip.explanation = (
            f"A round trip from {place_city(fare.origin) or fare.origin} to {city} for "
            f"{fare.currency} {round(fare.price)} total — the cheapest we found to {city} in your window."
        )
        trip.tags.extend(build_tags(trip))
        trips.append(trip)

    mark_relative_tags(trips)
    return sorted(trips, key=lambda t: (-t.dealScore, -(t.fitScore or 0), t.totalPrice))


def parse_iso_date(value: str | None):
    from datetime import date as _date

    if not value:
        return None
    try:
        return _date.fromisoformat(value[:10])
    except ValueError:
        return None


def merge_trip_options(paired: list[TripOption], bundles: list[TripOption]) -> list[TripOption]:
    """Combine one-way-paired trips with round-trip bundles.

    When both exist for the same origin->destination, keep the cheaper one (a
    round-trip bundle usually beats two summed one-ways). Re-rank by deal score,
    then fit, then price, and cap the result.
    """
    by_route: dict[tuple[str, str], TripOption] = {}
    order: list[tuple[str, str]] = []
    for trip in paired + bundles:
        key = (trip.outboundFlight.origin, trip.outboundFlight.destination)
        existing = by_route.get(key)
        if existing is None:
            by_route[key] = trip
            order.append(key)
        elif trip.totalPrice < existing.totalPrice:
            by_route[key] = trip

    merged = [by_route[key] for key in order]
    mark_relative_tags(merged)
    return sorted(
        merged,
        key=lambda trip: (
            -trip.dealScore,
            -(trip.fitScore or 0),
            trip.totalPrice,
        ),
    )[:30]
