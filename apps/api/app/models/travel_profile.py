from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TripType = Literal[
    "weekend_city_break",
    "beach",
    "food",
    "culture",
    "nature",
    "nightlife",
    "cheap_adventure",
    "long_haul_dream",
]
BudgetComfortZone = Literal["under_100", "under_200", "under_400", "flexible"]
Spontaneity = Literal["tomorrow", "next_week", "next_month", "planning_ahead"]
ComfortRule = Literal[
    "direct_only",
    "max_one_stop",
    "avoid_overnight_layovers",
    "no_departures_before_6am",
    "no_returns_after_midnight",
    "cabin_bag_included",
]
OpenJawWillingness = Literal["simple_returns_only", "nearby_city_open_jaw", "adventurous_multi_city"]
NotificationFrequency = Literal["instant_email", "weekly_digest", "urgent_only", "push_later"]


class TravelProfileUpdateRequest(BaseModel):
    homeLocation: str | None = Field(default=None, max_length=160)
    originAirports: list[str] = Field(min_length=1, max_length=12)
    maxAirportTravelTimeMinutes: int = Field(default=120, ge=10, le=600)
    preferredTripTypes: list[TripType] = Field(default_factory=list, max_length=8)
    preferredTripLengthMin: int = Field(default=2, ge=1, le=30)
    preferredTripLengthMax: int = Field(default=7, ge=1, le=30)
    budgetComfortZone: BudgetComfortZone = "under_200"
    spontaneity: Spontaneity = "next_month"
    comfortRules: list[ComfortRule] = Field(default_factory=list, max_length=6)
    openJawWillingness: OpenJawWillingness = "simple_returns_only"
    notificationFrequency: NotificationFrequency = "weekly_digest"
    excludedAirlines: list[str] = Field(default_factory=list, max_length=20)
    preferredMonths: list[int] = Field(default_factory=list, max_length=12)

    @field_validator("originAirports", "excludedAirlines")
    @classmethod
    def normalize_codes(cls, value: list[str]) -> list[str]:
        normalized = []
        for code in value:
            code = code.strip().upper()
            if not (2 <= len(code) <= 3) or not code.isalpha():
                raise ValueError(f"'{code}' is not a valid IATA code.")
            if code not in normalized:
                normalized.append(code)
        return normalized

    @field_validator("preferredMonths")
    @classmethod
    def validate_months(cls, value: list[int]) -> list[int]:
        if any(month < 1 or month > 12 for month in value):
            raise ValueError("preferredMonths must contain month numbers 1-12.")
        return sorted(set(value))

    @field_validator("preferredTripLengthMax")
    @classmethod
    def validate_length_range(cls, value: int, info) -> int:
        minimum = info.data.get("preferredTripLengthMin")
        if minimum is not None and value < minimum:
            raise ValueError("preferredTripLengthMax must be >= preferredTripLengthMin.")
        return value


class TravelProfileResponse(TravelProfileUpdateRequest):
    userId: str
    isComplete: bool = True
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


def default_profile_response(user_id: str) -> TravelProfileResponse:
    return TravelProfileResponse(
        userId=user_id,
        isComplete=False,
        originAirports=["VIE"],
    )
