from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models import ProviderMetadata, TripOption


Frequency = Literal["daily", "weekly"]
TripStyle = Literal["one city", "two nearby cities", "surprise me"]


class CreateSavedSearchRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=160)
    originAirports: list[str] = Field(min_length=1, max_length=12)
    destinationAirports: list[str] | None = Field(default=None, min_length=1, max_length=20)
    startDate: date
    endDate: date
    minTripLengthDays: int = Field(ge=1)
    maxTripLengthDays: int = Field(ge=1)
    maxBudget: float = Field(ge=20, le=5000)
    maxGroundTransferHours: float = Field(ge=0, le=12)
    tripStyle: TripStyle
    directOnly: bool | None = None
    includeBaggage: bool | None = None
    frequency: Frequency = "daily"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("originAirports")
    @classmethod
    def normalize_airports(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(code.strip().upper() for code in value if code.strip()))

    @field_validator("destinationAirports")
    @classmethod
    def normalize_destinations(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(code.strip().upper() for code in value if code.strip())) or None


class UpdateSavedSearchRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    originAirports: list[str] | None = Field(default=None, min_length=1, max_length=12)
    destinationAirports: list[str] | None = Field(default=None, max_length=20)
    startDate: date | None = None
    endDate: date | None = None
    minTripLengthDays: int | None = Field(default=None, ge=1)
    maxTripLengthDays: int | None = Field(default=None, ge=1)
    maxBudget: float | None = Field(default=None, ge=20, le=5000)
    maxGroundTransferHours: float | None = Field(default=None, ge=0, le=12)
    tripStyle: TripStyle | None = None
    directOnly: bool | None = None
    includeBaggage: bool | None = None
    frequency: Frequency | None = None

    @field_validator("originAirports")
    @classmethod
    def normalize_airports(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(code.strip().upper() for code in value if code.strip()))


class SavedSearchResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    originAirports: list[str]
    destinationAirports: list[str] | None = None
    startDate: date
    endDate: date
    minTripLengthDays: int
    maxTripLengthDays: int
    maxBudget: float
    maxGroundTransferHours: float
    tripStyle: str
    directOnly: bool | None = None
    includeBaggage: bool | None = None
    frequency: str
    isActive: bool
    createdAt: datetime
    lastCheckedAt: datetime | None = None
    lastNotifiedAt: datetime | None = None
    lastBestPrice: float | None = None
    lastBestTripId: str | None = None
    manageUrl: str | None = None
    unsubscribeUrl: str | None = None


class AlertPreviewResponse(BaseModel):
    savedSearch: SavedSearchResponse
    matchingTrips: list[TripOption]
    providerMetadata: ProviderMetadata | None = None


class AlertRunResponse(BaseModel):
    savedSearchId: str
    status: str
    resultCount: int = 0
    bestPrice: float | None = None
    notificationSent: bool = False
    warnings: list[str] = []
