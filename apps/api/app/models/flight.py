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
