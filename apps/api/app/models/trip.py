from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.flight import Flight
from app.models.transfer import GroundTransfer


class TripSearchRequest(BaseModel):
    originAirports: list[str] = Field(min_length=1)
    # None means "anywhere" — the classic Triplet surprise search.
    destinationAirports: list[str] | None = Field(default=None, min_length=1, max_length=20)
    destinationCountries: list[str] = Field(default_factory=list, max_length=20)
    destinationRegions: list[str] = Field(default_factory=list, max_length=8)
    destinationContinents: list[str] = Field(default_factory=list, max_length=7)
    excludeEurope: bool = False
    unvisitedOnly: bool = False
    # Multi-city: when set, return legs are searched from these airports and the
    # trip is built as an open-jaw with the between-cities journey estimated,
    # not filtered out by the ground-transfer limit.
    returnOriginAirports: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=20,
        description=(
            "Multi-city only: airports the traveller DEPARTS FROM on the return leg, when they "
            "name a different city than the outbound destination. Example: 'Budapest to Stockholm, "
            "then from Helsinki back to Budapest' -> destinationAirports=['STO'], "
            "returnOriginAirports=['HEL'] (never the home airport, which stays in originAirports)."
        ),
    )
    startDate: date
    endDate: date
    minTripLengthDays: int = Field(ge=1)
    maxTripLengthDays: int = Field(ge=1)
    maxBudget: float = Field(gt=0)
    maxGroundTransferHours: float = Field(ge=0)
    tripStyle: Literal["one city", "two nearby cities", "surprise me"]
    # What shape of trip to build. "return" is the default everywhere: out and
    # back from the same city. "open_jaw" flies into one city and home from
    # another, crossing between them on the ground. "multi_city" flies every hop.
    tripPlan: Literal["return", "open_jaw", "multi_city"] = "return"
    # Ordered cities to visit, for multi_city. Unlike destinationAirports (a set
    # of candidates, "any of these"), the order here is the itinerary.
    routeStops: list[str] | None = Field(default=None, min_length=2, max_length=6)
    # Connections are normal on long-haul routes. Users can still require direct
    # flights explicitly, but the worldwide default must not hide useful trips.
    directOnly: bool = False
    includeBaggage: bool = False
    # Optional per-search travel styles (destination-style keys like "beach",
    # "food"). When set, they override the profile's styles for this search and
    # boost the fit score of matching destinations.
    travelStyles: list[str] = Field(default_factory=list, max_length=9)


class ScoreComponent(BaseModel):
    label: str
    points: int


class TripSegment(BaseModel):
    """One move in a trip: a flight we price, or a ground hop we only estimate.

    Multi-city and open-jaw trips are chains of these. Ground segments carry a
    duration and a rough cost so the traveller can plan, but that cost is never
    added to the trip total — Triplet prices flights, and a train fare it has not
    looked up would be a number pretending to be a quote.
    """

    kind: Literal["flight", "ground"]
    origin: str
    destination: str
    originCity: str
    destinationCity: str
    departureDate: date
    flight: Flight | None = None
    transfer: GroundTransfer | None = None
    #: Where to check this hop's own price. A chained trip is priced as separate
    #: one-way tickets, so each one has to be checkable on its own.
    bookingUrl: str | None = None


class CityStay(BaseModel):
    """A city the traveller sleeps in, and for how long."""

    code: str
    city: str
    country: str
    countryCode: str
    arrivalDate: date
    departureDate: date
    nights: int


class DestinationMetadata(BaseModel):
    code: str
    kind: Literal["airport", "city"]
    city: str
    country: str
    countryCode: str
    continent: str | None = None


class TripOption(BaseModel):
    id: str
    tripType: Literal["same_city", "open_jaw", "multi_city"]
    # outboundFlight/returnFlight stay the first and last flights of the trip, so
    # every existing caller keeps working; `segments` carries the full chain.
    outboundFlight: Flight
    returnFlight: Flight
    groundTransfer: GroundTransfer | None
    segments: list[TripSegment] = []
    stays: list[CityStay] = []
    #: Sum of every flight fare. This is what totalPrice reports.
    flightCost: float = 0.0
    #: Rough cost of the ground hops, for planning only — never in totalPrice.
    groundEstimate: float | None = None
    totalPrice: float
    tripLengthDays: int
    nights: int
    score: int
    dealScore: int = 0
    fitScore: int | None = None
    dealScoreBreakdown: list[ScoreComponent] = []
    fitScoreBreakdown: list[ScoreComponent] = []
    suggestionId: str | None = None
    # two_one_ways: total is the sum of two independent one-way fares (pairing).
    # round_trip_bundle: total is a single round-trip fare; per-leg prices unknown.
    fareKind: Literal["two_one_ways", "round_trip_bundle"] = "two_one_ways"
    explanation: str
    warnings: list[str]
    tags: list[str]
    bookingUrl: str | None = None
    bookingLabel: str | None = None
    affiliateUrl: str | None = None
    providerDeepLink: str | None = None
    outboundBookingUrl: str | None = None
    returnBookingUrl: str | None = None
    provider: str | None = None
    linkType: Literal["provider_deeplink", "affiliate_referral", "none"] = "none"
    destination: DestinationMetadata | None = None


class ProviderMetadata(BaseModel):
    providerUsed: str | None = None
    providerName: str | None = None
    liveProviderAttempted: bool = False
    liveProviderSucceeded: bool = False
    cachedResultsUsed: bool = False
    cachedResultsStale: bool = False
    requestsAttempted: int | None = None
    requestsLimit: int | None = None
    rawOffersCount: int | None = None
    mappedFlightsCount: int | None = None
    skippedOffersCount: int | None = None
    affiliateLinksGenerated: int | None = None
    deepLinksReturned: int | None = None
    providerWarnings: list[str] = []


class TripSearchResponse(BaseModel):
    trips: list[TripOption]
    # Set when nothing matched exactly and we fell back to the closest real
    # fares; says what was loosened so results are never silently different.
    relaxationNote: str | None = None
    providerUsed: str | None = None
    providerWarnings: list[str] = []
    cachedResultsUsed: bool = False
    providerMetadata: ProviderMetadata | None = None
