from app.models import Airport, Flight, GroundTransfer, TripOption, TripSearchRequest
from app.services.trip_explainer import build_explanation, build_tags, build_warnings
from app.services.trip_scoring import calculate_trip_score


def build_trips(
    request: TripSearchRequest,
    airports: list[Airport],
    flights: list[Flight],
    transfers: list[GroundTransfer],
) -> list[TripOption]:
    airports_by_code = {airport.code: airport for airport in airports}
    origin_codes = {code.upper() for code in request.originAirports}
    outbound_candidates = [
        flight
        for flight in flights
        if flight.origin in origin_codes
        and request.startDate <= flight.departureDateTime.date() <= request.endDate
    ]

    trips: list[TripOption] = []

    for outbound in outbound_candidates:
        if outbound.destination not in airports_by_code:
            continue

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
            trip.score = calculate_trip_score(trip, request)
            trip.explanation = build_explanation(trip, request, airports_by_code)
            trip.tags = build_tags(trip)
            trips.append(trip)

    mark_relative_tags(trips)
    return sorted(
        trips,
        key=lambda trip: (
            -trip.score,
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


def pick_trip_provider(outbound: Flight, return_flight: Flight) -> str | None:
    if outbound.provider == return_flight.provider:
        return outbound.provider
    if "skyscanner" in {outbound.provider, return_flight.provider}:
        return "skyscanner"
    return outbound.provider or return_flight.provider


def pick_trip_deep_link(outbound: Flight, return_flight: Flight) -> str | None:
    if outbound.deepLink:
        return outbound.deepLink
    if return_flight.deepLink:
        return return_flight.deepLink
    if outbound.provider == "skyscanner" and outbound.bookingUrl:
        return outbound.bookingUrl
    if return_flight.provider == "skyscanner" and return_flight.bookingUrl:
        return return_flight.bookingUrl
    return None


def pick_trip_affiliate_url(outbound: Flight, return_flight: Flight) -> str | None:
    for flight in (outbound, return_flight):
        if flight.provider == "skyscanner" and flight.bookingUrl and not flight.deepLink:
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
        return "View on Skyscanner"
    if link_type == "affiliate_referral":
        return "Check price"
    return None
