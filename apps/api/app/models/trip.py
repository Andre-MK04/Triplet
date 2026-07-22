from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.flight import Flight
from app.models.transfer import GroundTransfer


class TripSearchRequest(BaseModel):
    originAirports: list[str] = Field(min_length=1)
    # None means "anywhere" — the classic Triplet surprise search.
    destinationAirports: list[str] | None = Field(default=None, min_length=1, max_length=20)
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
    directOnly: bool = True
    includeBaggage: bool = False
    # Optional per-search travel styles (destination-style keys like "beach",
    # "food"). When set, they override the profile's styles for this search and
    # boost the fit score of matching destinations.
    travelStyles: list[str] = Field(default_factory=list, max_length=9)


class ScoreComponent(BaseModel):
    label: str
    points: int


class TripOption(BaseModel):
    id: str
    tripType: Literal["same_city", "open_jaw"]
    outboundFlight: Flight
    returnFlight: Flight
    groundTransfer: GroundTransfer | None
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
    providerUsed: str | None = None
    providerWarnings: list[str] = []
    cachedResultsUsed: bool = False
    providerMetadata: ProviderMetadata | None = None
