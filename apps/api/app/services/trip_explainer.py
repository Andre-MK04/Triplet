from app.data.destination_styles import destination_styles, style_labels
from app.models import Airport, Flight, GroundTransfer, TripOption, TripSearchRequest


def airport_label(code: str, airports_by_code: dict[str, Airport]) -> str:
    airport = airports_by_code.get(code)
    if not airport:
        return code
    return airport.city


def airport_area(code: str, airports_by_code: dict[str, Airport]) -> str:
    airport = airports_by_code.get(code)
    return airport.areaName if airport and airport.areaName else airport_label(code, airports_by_code)


def build_explanation(
    trip: TripOption,
    request: TripSearchRequest,
    airports_by_code: dict[str, Airport],
) -> str:
    outbound_origin = airport_label(trip.outboundFlight.origin, airports_by_code)
    outbound_destination = airport_area(trip.outboundFlight.destination, airports_by_code)
    return_origin = airport_area(trip.returnFlight.origin, airports_by_code)
    return_destination = airport_label(trip.returnFlight.destination, airports_by_code)
    budget_phrase = f"stays under your €{request.maxBudget:g} budget"

    if trip.groundTransfer:
        return (
            f"This open-jaw trip works because the outbound flight to {outbound_destination} is cheap, "
            f"the return flight from {return_origin} is also cheap, and "
            f"{trip.groundTransfer.fromCity} to {trip.groundTransfer.toCity} is a manageable "
            f"{trip.groundTransfer.durationHours:g}-hour ground transfer. You get a two-city trip that {budget_phrase}."
        )

    return (
        f"This is a simple return-style trip. You fly from {outbound_origin} to {outbound_destination} "
        f"and return from {return_origin} to {return_destination} {trip.nights} days later. "
        f"It {budget_phrase} and does not require a ground transfer."
    )


def build_warnings(
    outbound: Flight,
    return_flight: Flight,
    ground_transfer: GroundTransfer | None,
    nights: int,
    include_baggage: bool,
) -> list[str]:
    warnings = ["Separate tickets: this trip is built from independent one-way flights."]

    if ground_transfer:
        warnings.append(f"Ground transfer required between {ground_transfer.fromCity} and {ground_transfer.toCity}.")
        if ground_transfer.durationHours > 3:
            warnings.append("Long ground transfer.")

    if outbound.departureDateTime.hour < 6:
        warnings.append("Early outbound departure.")
    if outbound.arrivalDateTime.hour >= 23:
        warnings.append("Late outbound arrival.")
    if return_flight.departureDateTime.hour < 6:
        warnings.append("Early return departure.")
    if return_flight.arrivalDateTime.hour >= 23:
        warnings.append("Late return arrival.")
    if include_baggage and (not outbound.baggageIncluded or not return_flight.baggageIncluded):
        warnings.append("Baggage may not be included.")
    if nights < 3:
        warnings.append("Very short trip.")

    return warnings


def build_tags(trip: TripOption) -> list[str]:
    tags: list[str] = []

    if trip.tripType == "open_jaw":
        tags.append("Two-city trip")
    else:
        tags.append("No ground transfer")

    styles = destination_styles(trip.outboundFlight.destination, trip.returnFlight.origin)
    tags.extend(style_labels(styles))

    if trip.groundTransfer and trip.groundTransfer.durationHours <= 2.5:
        tags.append("Easy transfer")
    if trip.totalPrice < 100:
        tags.append("Under €100")
    if trip.nights in {3, 4}:
        tags.append("Weekend-friendly")
    if trip.outboundFlight.departureDateTime.hour < 6 or trip.returnFlight.departureDateTime.hour < 6:
        tags.append("Early flight")
    if trip.outboundFlight.arrivalDateTime.hour >= 23 or trip.returnFlight.arrivalDateTime.hour >= 23:
        tags.append("Late arrival")

    return tags
