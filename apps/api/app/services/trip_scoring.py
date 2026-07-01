from app.models import TripOption, TripSearchRequest


def calculate_trip_score(trip: TripOption, request: TripSearchRequest) -> int:
    score = 100

    price_ratio = trip.totalPrice / request.maxBudget
    if price_ratio <= 0.4:
        score -= 0
    elif price_ratio <= 0.6:
        score -= 5
    elif price_ratio <= 0.8:
        score -= 12
    else:
        score -= 22

    if trip.groundTransfer:
        if trip.groundTransfer.durationHours <= 2:
            score -= 5
        elif trip.groundTransfer.durationHours <= 4:
            score -= 12
        else:
            score -= 25

    if trip.outboundFlight.departureDateTime.hour < 6:
        score -= 8
    if trip.outboundFlight.arrivalDateTime.hour >= 23:
        score -= 8
    if trip.returnFlight.departureDateTime.hour < 6:
        score -= 8
    if trip.returnFlight.arrivalDateTime.hour >= 23:
        score -= 8

    if trip.nights < 3:
        score -= 15
    elif trip.nights > 10:
        score -= 8

    if trip.tripType == "open_jaw" and trip.groundTransfer:
        if trip.groundTransfer.durationHours <= 3:
            score += 5
        else:
            score -= 8

    if request.includeBaggage and (
        not trip.outboundFlight.baggageIncluded or not trip.returnFlight.baggageIncluded
    ):
        score -= 10

    return max(0, min(100, score))
