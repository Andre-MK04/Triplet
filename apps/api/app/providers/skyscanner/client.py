import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.providers.errors import (
    ProviderApiError,
    ProviderAuthError,
    ProviderConfigError,
    ProviderMappingError,
    ProviderNoResultsError,
    ProviderRateLimitError,
)

logger = logging.getLogger(__name__)


class SkyscannerConfigError(ProviderConfigError):
    pass


class SkyscannerAuthError(ProviderAuthError):
    pass


class SkyscannerApiError(ProviderApiError):
    pass


class SkyscannerRateLimitError(SkyscannerApiError, ProviderRateLimitError):
    pass


class SkyscannerNoResultsError(SkyscannerApiError, ProviderNoResultsError):
    pass


class SkyscannerMappingError(ProviderMappingError):
    pass


class SkyscannerHttpClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        poll_attempts: int | None = None,
        poll_delay_seconds: float | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.skyscanner_api_key
        self.base_url = (base_url or settings.skyscanner_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.skyscanner_timeout_seconds
        self.poll_attempts = poll_attempts or settings.skyscanner_poll_attempts
        self.poll_delay_seconds = poll_delay_seconds or settings.skyscanner_poll_delay_seconds

    def create_live_price_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/apiservices/v3/flights/live/search/create", payload)

    def poll_live_price_search(self, session_token: str) -> dict[str, Any]:
        return self._post(f"/apiservices/v3/flights/live/search/poll/{session_token}", {})

    def run_live_price_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        created = self.create_live_price_search(payload)
        session_token = extract_session_token(created)
        if not session_token:
            return created

        latest = created
        for attempt in range(self.poll_attempts):
            latest = self.poll_live_price_search(session_token)
            if is_search_complete(latest):
                break
            if attempt < self.poll_attempts - 1:
                time.sleep(self.poll_delay_seconds)
        return latest

    def search_indicative_prices(self, payload: dict[str, Any]) -> dict[str, Any]:
        # TODO: wire Skyscanner Indicative Prices once API access/shape is confirmed.
        raise SkyscannerApiError("Skyscanner indicative prices are not implemented yet.")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise SkyscannerConfigError("Skyscanner API key is missing.")
        url = f"{self.base_url}{path}"
        logger.debug("Skyscanner POST %s", path)
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise SkyscannerApiError("Skyscanner request timed out.") from exc
        except httpx.HTTPError as exc:
            raise SkyscannerApiError("Skyscanner request failed.") from exc

        if response.status_code in {401, 403}:
            raise SkyscannerAuthError("Skyscanner authentication failed.")
        if response.status_code == 429:
            raise SkyscannerRateLimitError("Skyscanner rate limit reached.")
        if response.status_code >= 500:
            raise SkyscannerApiError(f"Skyscanner API error: HTTP {response.status_code}.")
        if response.status_code >= 400:
            raise SkyscannerApiError(f"Skyscanner API request was rejected: HTTP {response.status_code}.")

        payload = response.json()
        if not payload:
            raise SkyscannerNoResultsError("Skyscanner returned no data.")
        return payload


def extract_session_token(payload: dict[str, Any]) -> str | None:
    return (
        payload.get("sessionToken")
        or payload.get("session_token")
        or payload.get("token")
        or (payload.get("content") or {}).get("sessionToken")
    )


def is_search_complete(payload: dict[str, Any]) -> bool:
    status = (
        payload.get("status")
        or payload.get("sessionStatus")
        or (payload.get("content") or {}).get("status")
        or ""
    )
    return str(status).lower() in {"complete", "completed", "results_complete"}
