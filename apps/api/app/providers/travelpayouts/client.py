import logging
from typing import Any

import httpx

from app.config import settings
from app.providers.errors import (
    ProviderApiError,
    ProviderAuthError,
    ProviderConfigError,
    ProviderRateLimitError,
)

logger = logging.getLogger(__name__)


class TravelpayoutsConfigError(ProviderConfigError):
    pass


class TravelpayoutsAuthError(ProviderAuthError):
    pass


class TravelpayoutsApiError(ProviderApiError):
    pass


class TravelpayoutsRateLimitError(TravelpayoutsApiError, ProviderRateLimitError):
    pass


class TravelpayoutsHttpClient:
    """Travelpayouts/Aviasales Data API client. Cached market prices, not live availability."""

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.api_token = api_token if api_token is not None else settings.travelpayouts_api_token
        self.base_url = (base_url or settings.travelpayouts_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.travelpayouts_timeout_seconds

    def prices_for_dates(
        self,
        origin: str,
        destination: str,
        departure_at: str,
        one_way: bool = True,
        limit: int = 30,
    ) -> dict[str, Any]:
        return self._get(
            "/aviasales/v3/prices_for_dates",
            {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "departure_at": departure_at,
                "one_way": str(one_way).lower(),
                "unique": "false",
                "sorting": "price",
                "direct": "false",
                "currency": settings.travelpayouts_currency.lower(),
                "limit": limit,
            },
        )

    def city_directions(self, origin: str, currency: str | None = None) -> dict[str, Any]:
        """Cheapest cached fares from an origin to every popular destination.

        This is the "anywhere" primitive: the provider discovers destinations
        for us, so the search is not limited to a hardcoded destination list.
        """
        return self._get(
            "/v1/city-directions",
            {
                "origin": origin.upper(),
                "currency": (currency or settings.travelpayouts_currency).lower(),
            },
        )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_token:
            raise TravelpayoutsConfigError("Travelpayouts API token is not configured.")
        response = httpx.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"X-Access-Token": self.api_token, "Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        if response.status_code in (401, 403):
            raise TravelpayoutsAuthError("Travelpayouts rejected the API token.")
        if response.status_code == 429:
            raise TravelpayoutsRateLimitError("Travelpayouts rate limit reached.")
        if response.status_code >= 400:
            raise TravelpayoutsApiError(f"Travelpayouts API error (HTTP {response.status_code}).")
        try:
            return response.json()
        except ValueError as exc:
            raise TravelpayoutsApiError("Travelpayouts returned a non-JSON response.") from exc
