from typing import Literal

from pydantic import BaseModel


class GroundTransfer(BaseModel):
    fromAirport: str
    toAirport: str
    fromCity: str
    toCity: str
    durationHours: float
    estimatedCost: float
    mode: Literal["train/bus", "train", "bus", "car"]
