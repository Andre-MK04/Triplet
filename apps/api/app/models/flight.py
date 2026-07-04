from datetime import datetime

from pydantic import BaseModel


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
    agentName: str | None = None
    stops: int | None = None
    durationMinutes: int | None = None
    isLive: bool = False
