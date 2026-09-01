from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import ProviderMetadata, TripOption


Frequency = Literal["daily", "weekly"]

#: What makes a watch worth an email — a separate question from how often it may
#: send one. Only the four the runner actually implements are offered; a choice
#: the backend cannot honour would be worse than no choice.
TriggerMode = Literal["any", "below_budget", "route_deal", "price_drop"]
TripStyle = Literal["one city", "two nearby cities", "surprise me"]


class CreateSavedSearchRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=160)
    originAirports: list[str] = Field(min_length=1, max_length=12)
    destinationAirports: list[str] | None = Field(default=None, min_length=1, max_length=20)
    destinationCountries: list[str] = Field(default_factory=list, max_length=20)
    destinationRegions: list[str] = Field(default_factory=list, max_length=8)
    destinationContinents: list[str] = Field(default_factory=list, max_length=7)
    excludeEurope: bool = False
    unvisitedOnly: bool = False
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
    #: None means "use the account's preference, or any". Kept optional so an
    #: older client that does not know about triggers still creates a working watch.
    triggerMode: TriggerMode | None = None

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

    @model_validator(mode="after")
    def reject_unpersisted_geographic_scope(self):
        if (
            self.destinationCountries
            or self.destinationRegions
            or self.destinationContinents
            or self.excludeEurope
            or self.unvisitedOnly
        ):
            raise ValueError(
                "Country, region, continent, outside-Europe, and unvisited-only watches are not persisted yet. "
                "Choose a city/airport or save an anywhere watch."
            )
        return self


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
    triggerMode: TriggerMode | None = None

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
    triggerMode: str | None = None
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


class WatchPricePoint(BaseModel):
    checkedAt: datetime
    bestPrice: float | None = None
    resultCount: int
    status: str


class WatchDeliveryStatus(BaseModel):
    sentAt: datetime
    status: str
    provider: str
    subject: str


class WatchInsightsResponse(BaseModel):
    savedSearchId: str
    alertTriggerMode: str
    totalChecks: int
    successfulChecks: int
    notificationCount: int
    currentBestPrice: float | None = None
    lowestObservedPrice: float | None = None
    averageObservedPrice: float | None = None
    changeFromPrevious: float | None = None
    budgetHeadroom: float | None = None
    history: list[WatchPricePoint]
    deliveries: list[WatchDeliveryStatus]
