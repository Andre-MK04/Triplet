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


class DuffelConfigError(ProviderConfigError):
    pass


class DuffelAuthError(ProviderAuthError):
    pass


class DuffelApiError(ProviderApiError):
    pass


class DuffelRateLimitError(DuffelApiError, ProviderRateLimitError):
    pass


class DuffelHttpClient:
    """Minimal Duffel Flights API client. Search/offers only; Triplet never books."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.duffel_api_key
        self.base_url = (base_url or settings.duffel_base_url).rstrip("/")
        self.api_version = api_version or settings.duffel_api_version
        self.timeout_seconds = timeout_seconds or settings.duffel_timeout_seconds

    def create_offer_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/air/offer_requests?return_offers=true", payload)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise DuffelConfigError("Duffel API key is not configured.")
        response = httpx.post(
            f"{self.base_url}{path}",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Duffel-Version": self.api_version,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code in (401, 403):
            raise DuffelAuthError("Duffel rejected the API key.")
        if response.status_code == 429:
            raise DuffelRateLimitError("Duffel rate limit reached.")
        if response.status_code >= 400:
            # Never log or raise with the response body: it can echo request details.
            raise DuffelApiError(f"Duffel API error (HTTP {response.status_code}).")
        try:
            return response.json()
        except ValueError as exc:
            raise DuffelApiError("Duffel returned a non-JSON response.") from exc
