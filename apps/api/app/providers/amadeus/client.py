import logging
from typing import Any

import httpx

from app.config import settings
from app.providers.amadeus.auth import AmadeusAuthClient

logger = logging.getLogger(__name__)


class AmadeusConfigError(RuntimeError):
    pass


class AmadeusAuthError(RuntimeError):
    pass


class AmadeusApiError(RuntimeError):
    pass


class AmadeusRateLimitError(AmadeusApiError):
    pass


class AmadeusNoResultsError(AmadeusApiError):
    pass


class AmadeusHttpClient:
    def __init__(
        self,
        auth_client: AmadeusAuthClient | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.auth_client = auth_client or AmadeusAuthClient()
        self.base_url = (base_url or settings.amadeus_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.amadeus_timeout_seconds

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        token = self.auth_client.get_access_token()
        url = f"{self.base_url}{path}"
        safe_params = {key: value for key, value in params.items() if key.lower() not in {"client_secret"}}
        logger.debug("Amadeus GET %s params=%s", path, safe_params)

        try:
            response = httpx.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AmadeusApiError("Amadeus request failed.") from exc

        if response.status_code == 429:
            raise AmadeusRateLimitError("Amadeus rate limit reached.")
        if response.status_code == 401:
            raise AmadeusAuthError("Amadeus authentication failed.")
        if response.status_code >= 400:
            raise AmadeusApiError(f"Amadeus API error: HTTP {response.status_code}.")

        payload = response.json()
        if not payload.get("data"):
            raise AmadeusNoResultsError("Amadeus returned no flight offers.")
        return payload
