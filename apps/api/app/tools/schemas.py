from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.models import Airport, GroundTransfer, ProviderMetadata, TripOption, TripSearchRequest


class SearchTripsInput(TripSearchRequest):
    pass


class SearchTripsOutput(BaseModel):
    trips: list[TripOption]
    providerUsed: str | None = None
    providerWarnings: list[str] = []
    cachedResultsUsed: bool = False
    providerMetadata: ProviderMetadata | None = None


class GetAirportsInput(BaseModel):
    originCandidatesOnly: bool = False
    country: str | None = None
    query: str | None = None


class GetAirportsOutput(BaseModel):
    airports: list[Airport]


class EstimateGroundTransferInput(BaseModel):
    fromAirport: str
    toAirport: str


class EstimateGroundTransferOutput(BaseModel):
    exists: bool
    transfer: GroundTransfer | None = None
    message: str


class ExplainTripInput(BaseModel):
    trip: TripOption
    userPreferences: dict[str, Any] | None = None


class ExplainTripOutput(BaseModel):
    explanation: str
    warnings: list[str]
    tags: list[str]


class ParseTripIntentInput(BaseModel):
    message: str = Field(min_length=1)


class ParsedTripIntent(BaseModel):
    originAirports: list[str] = []
    destinationAirports: list[str] | None = None
    startDate: date | None = None
    endDate: date | None = None
    minTripLengthDays: int | None = None
    maxTripLengthDays: int | None = None
    maxBudget: float | None = None
    maxGroundTransferHours: float = 4
    tripStyle: str | None = None
    directOnly: bool = False
    includeBaggage: bool = False
    parsedSearch: TripSearchRequest | None = None
    missingFields: list[str] = []
    confidence: float
    notes: str


class ParseTripIntentOutput(ParsedTripIntent):
    pass
