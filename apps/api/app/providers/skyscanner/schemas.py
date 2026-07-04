from pydantic import BaseModel


class SkyscannerLiveSearchSummary(BaseModel):
    configured: bool
    apiOk: bool
    rawOffersCount: int = 0
    mappedFlightsCount: int = 0
    skippedOffersCount: int = 0
    deepLinksReturned: int = 0
    warnings: list[str] = []
