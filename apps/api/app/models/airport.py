from pydantic import BaseModel


class Airport(BaseModel):
    code: str
    name: str
    city: str
    country: str
    latitude: float | None = None
    longitude: float | None = None
    isUserOriginCandidate: bool = False
    areaSlug: str | None = None
    areaName: str | None = None
