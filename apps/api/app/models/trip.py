from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.flight import Flight
from app.models.transfer import GroundTransfer


class TripSearchRequest(BaseModel):
    originAirports: list[str] = Field(min_length=1)
    startDate: date
    endDate: date
    minTripLengthDays: int = Field(ge=1)
    maxTripLengthDays: int = Field(ge=1)
    maxBudget: float = Field(gt=0)
    maxGroundTransferHours: float = Field(ge=0)
    tripStyle: Literal["one city", "two nearby cities", "surprise me"]
    directOnly: bool = True
    includeBaggage: bool = False


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
    explanation: str
    warnings: list[str]
    tags: list[str]


class ProviderMetadata(BaseModel):
    providerUsed: str | None = None
    liveProviderAttempted: bool = False
    liveProviderSucceeded: bool = False
    cachedResultsUsed: bool = False
    amadeusRequestsAttempted: int | None = None
    amadeusRequestsLimit: int | None = None
    rawOffersCount: int | None = None
    mappedFlightsCount: int | None = None
    providerWarnings: list[str] = []


class TripSearchResponse(BaseModel):
    trips: list[TripOption]
    providerUsed: str | None = None
    providerWarnings: list[str] = []
    cachedResultsUsed: bool = False
    providerMetadata: ProviderMetadata | None = None
