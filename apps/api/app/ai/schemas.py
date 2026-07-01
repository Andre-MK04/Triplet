from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models import ProviderMetadata, TripOption, TripSearchRequest
from app.tools.schemas import ParsedTripIntent, SearchTripsOutput


class ParseTripIntentRequest(BaseModel):
    message: str = Field(min_length=1)


class SearchPreviewRequest(BaseModel):
    message: str = Field(min_length=1)


class SearchPreviewResponse(BaseModel):
    intent: ParsedTripIntent
    results: SearchTripsOutput | None = None


class AISearchRequest(BaseModel):
    message: str = Field(min_length=1)
    originAirports: list[str] | None = None
    startDate: date | None = None
    endDate: date | None = None
    minTripLengthDays: int | None = None
    maxTripLengthDays: int | None = None
    maxBudget: float | None = None
    maxGroundTransferHours: float | None = None
    tripStyle: Literal["one city", "two nearby cities", "surprise me"] | None = None
    directOnly: bool | None = None
    includeBaggage: bool | None = None


class AIMetadata(BaseModel):
    aiProvider: str
    model: str
    toolCallsUsed: int = 0
    fallbackUsed: bool = False
    warnings: list[str] = []


class AISearchResponse(BaseModel):
    message: str
    parsedRequest: TripSearchRequest | None = None
    trips: list[TripOption] = []
    missingFields: list[str] = []
    confidence: float | None = None
    providerMetadata: ProviderMetadata | None = None
    aiMetadata: AIMetadata


class AIParseOnlyRequest(BaseModel):
    message: str = Field(min_length=1)


class AIParseOnlyResponse(BaseModel):
    parsedRequest: TripSearchRequest | None = None
    missingFields: list[str] = []
    confidence: float | None = None
    notes: str
