from datetime import datetime, timedelta

import httpx

from app.config import settings


class AmadeusAuthClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.client_id = client_id if client_id is not None else settings.amadeus_client_id
        self.client_secret = client_secret if client_secret is not None else settings.amadeus_client_secret
        self.base_url = (base_url or settings.amadeus_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.amadeus_timeout_seconds
        self._access_token: str | None = None
        self._expires_at: datetime | None = None

    def get_access_token(self) -> str:
        from app.providers.amadeus.client import AmadeusAuthError, AmadeusConfigError

        if self._access_token and self._expires_at and datetime.utcnow() < self._expires_at:
            return self._access_token

        if not self.client_id or not self.client_secret:
            raise AmadeusConfigError("Amadeus credentials are missing.")

        try:
            response = httpx.post(
                f"{self.base_url}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AmadeusAuthError("Could not authenticate with Amadeus.") from exc

        if response.status_code >= 400:
            raise AmadeusAuthError("Could not authenticate with Amadeus.")

        payload = response.json()
        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 0))
        if not access_token or expires_in <= 0:
            raise AmadeusAuthError("Invalid Amadeus token response.")

        self._access_token = access_token
        self._expires_at = datetime.utcnow() + timedelta(seconds=max(expires_in - 60, 1))
        return access_token
