from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


CountryStatus = Literal["visited", "lived", "wishlist", "unvisited"]
VisitKind = Literal["visit", "lived"]


class CountryCatalogEntry(BaseModel):
    code: str
    alpha3: str
    numericCode: str
    name: str
    continent: str
    countsTowardWorldTotal: bool


class CountryCatalogResponse(BaseModel):
    definition: str
    worldTotal: int
    continentTotal: int
    continents: list[str]
    countries: list[CountryCatalogEntry]


class CountryStateUpdate(BaseModel):
    visited: bool | None = None
    lived: bool | None = None
    wishlist: bool | None = None

    @model_validator(mode="after")
    def at_least_one_change(self):
        if self.visited is None and self.lived is None and self.wishlist is None:
            raise ValueError("At least one country state must be provided.")
        return self


class BulkCountryUpdate(BaseModel):
    countryCodes: list[str] = Field(min_length=1, max_length=195)
    status: Literal["visited", "lived", "wishlist"]
    enabled: bool = True


class VisitWriteRequest(BaseModel):
    kind: VisitKind = "visit"
    startDate: str | None = Field(default=None, max_length=10, description="YYYY, YYYY-MM, or YYYY-MM-DD")
    endDate: str | None = Field(default=None, max_length=10, description="YYYY, YYYY-MM, or YYYY-MM-DD")
    note: str | None = Field(default=None, max_length=1000)
    tripId: str | None = Field(default=None, max_length=36)


class VisitResponse(BaseModel):
    id: str
    countryCode: str
    kind: VisitKind
    startDate: str | None
    endDate: str | None
    startPrecision: Literal["exact", "month", "year", "unknown"]
    endPrecision: Literal["exact", "month", "year", "unknown"]
    note: str | None
    tripId: str | None
    createdAt: datetime
    updatedAt: datetime


class TravelMapCountryResponse(BaseModel):
    code: str
    name: str
    continent: str
    visited: bool
    lived: bool
    wishlist: bool
    primaryStatus: CountryStatus
    visitCount: int
    residenceCount: int
    visits: list[VisitResponse]
    updatedAt: datetime


class ContinentProgress(BaseModel):
    name: str
    visited: int
    total: int


class TravelMapStats(BaseModel):
    countriesVisited: int
    countriesLivedIn: int
    wishlistCountries: int
    worldTotal: int
    worldExploredPercentage: float
    continentsVisited: int
    continentTotal: int
    continentProgress: list[ContinentProgress]


class TravelMapResponse(BaseModel):
    countries: list[TravelMapCountryResponse]
    stats: TravelMapStats
    updatedAt: datetime | None
