from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ConfidenceLevel = Literal["live", "cached", "indicative", "mock"]


class Flight(BaseModel):
    id: str
    origin: str
    destination: str
    departureDateTime: datetime
    arrivalDateTime: datetime
    airline: str
    price: float
    currency: str = "EUR"
    bookingUrl: str | None = None
    baggageIncluded: bool = False
    provider: str = "mock"
    providerOfferId: str | None = None
    deepLink: str | None = None
    affiliateUrl: str | None = None
    agentName: str | None = None
    stops: int | None = None
    durationMinutes: int | None = None
    isLive: bool = False
    confidenceLevel: ConfidenceLevel = "mock"
    observedAt: datetime | None = None
    expiresAt: datetime | None = None
    rawProviderRef: str | None = None
