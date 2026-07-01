import secrets
import time
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode

import httpx
import jwt

from app.config import settings

OAuthProvider = Literal["google", "apple"]
OAUTH_STATE_COOKIE_NAME = "triplet_oauth_state"
OAUTH_PROVIDERS = {"google", "apple"}


class OAuthConfigError(ValueError):
    pass


class OAuthProviderError(ValueError):
    pass


@dataclass(frozen=True)
class OAuthProfile:
    provider: OAuthProvider
    provider_user_id: str
    email: str
    email_verified: bool
    display_name: str | None = None


def generate_oauth_state() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "nonce": secrets.token_urlsafe(24),
            "iat": now,
            "exp": now + 10 * 60,
            "typ": "oauth_state",
        },
        settings.app_secret,
        algorithm="HS256",
    )


def verify_oauth_state(state: str | None, cookie_state: str | None = None) -> bool:
    if not state:
        return False
    if cookie_state and not secrets.compare_digest(state, cookie_state):
        return False
    try:
        payload = jwt.decode(state, settings.app_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return False
    return payload.get("typ") == "oauth_state"


def validate_provider(provider: str) -> OAuthProvider:
    if provider not in OAUTH_PROVIDERS:
        raise OAuthConfigError("OAuth provider is not supported.")
    return provider  # type: ignore[return-value]


def authorization_url(provider: OAuthProvider, state: str) -> str:
    if provider == "google":
        client_id = _require(settings.google_oauth_client_id, "GOOGLE_OAUTH_CLIENT_ID")
        query = {
            "client_id": client_id,
            "redirect_uri": callback_url("google"),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(query)

    client_id = _require(settings.apple_oauth_client_id, "APPLE_OAUTH_CLIENT_ID")
    query = {
        "client_id": client_id,
        "redirect_uri": callback_url("apple"),
        "response_type": "code",
        "scope": "name email",
        "response_mode": "form_post",
        "state": state,
    }
    return "https://appleid.apple.com/auth/authorize?" + urlencode(query)


def callback_url(provider: OAuthProvider) -> str:
    return f"{settings.auth_public_base_url.rstrip('/')}/auth/oauth/{provider}/callback"


async def exchange_code_for_profile(provider: OAuthProvider, code: str) -> OAuthProfile:
    if provider == "google":
        return await _exchange_google_code(code)
    return await _exchange_apple_code(code)


async def _exchange_google_code(code: str) -> OAuthProfile:
    client_id = _require(settings.google_oauth_client_id, "GOOGLE_OAUTH_CLIENT_ID")
    client_secret = _require(settings.google_oauth_client_secret, "GOOGLE_OAUTH_CLIENT_SECRET")
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback_url("google"),
            },
        )
    if token_response.status_code >= 400:
        raise OAuthProviderError("Google sign-in failed.")
    id_token = token_response.json().get("id_token")
    if not id_token:
        raise OAuthProviderError("Google did not return an ID token.")

    claims = _decode_provider_id_token(
        id_token,
        jwks_url="https://www.googleapis.com/oauth2/v3/certs",
        audience=client_id,
        issuer="https://accounts.google.com",
    )
    email = claims.get("email")
    if not email:
        raise OAuthProviderError("Google account did not return an email address.")
    return OAuthProfile(
        provider="google",
        provider_user_id=claims["sub"],
        email=email.strip().lower(),
        email_verified=claims.get("email_verified") is True,
        display_name=claims.get("name"),
    )


async def _exchange_apple_code(code: str) -> OAuthProfile:
    client_id = _require(settings.apple_oauth_client_id, "APPLE_OAUTH_CLIENT_ID")
    client_secret = apple_client_secret()
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://appleid.apple.com/auth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback_url("apple"),
            },
        )
    if token_response.status_code >= 400:
        raise OAuthProviderError("Apple sign-in failed.")
    id_token = token_response.json().get("id_token")
    if not id_token:
        raise OAuthProviderError("Apple did not return an ID token.")

    claims = _decode_provider_id_token(
        id_token,
        jwks_url="https://appleid.apple.com/auth/keys",
        audience=client_id,
        issuer="https://appleid.apple.com",
    )
    email = claims.get("email")
    if not email:
        raise OAuthProviderError("Apple account did not return an email address.")
    return OAuthProfile(
        provider="apple",
        provider_user_id=claims["sub"],
        email=email.strip().lower(),
        email_verified=str(claims.get("email_verified")).lower() == "true",
    )


def apple_client_secret() -> str:
    if settings.apple_oauth_client_secret:
        return settings.apple_oauth_client_secret

    team_id = _require(settings.apple_oauth_team_id, "APPLE_OAUTH_TEAM_ID")
    key_id = _require(settings.apple_oauth_key_id, "APPLE_OAUTH_KEY_ID")
    client_id = _require(settings.apple_oauth_client_id, "APPLE_OAUTH_CLIENT_ID")
    private_key = _require(settings.apple_oauth_private_key, "APPLE_OAUTH_PRIVATE_KEY").replace("\\n", "\n")
    now = int(time.time())
    return jwt.encode(
        {
            "iss": team_id,
            "iat": now,
            "exp": now + 60 * 60 * 24 * 30,
            "aud": "https://appleid.apple.com",
            "sub": client_id,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": key_id},
    )


def _decode_provider_id_token(id_token: str, jwks_url: str, audience: str, issuer: str) -> dict:
    try:
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise OAuthProviderError("OAuth ID token could not be verified.") from exc


def _require(value: str | None, name: str) -> str:
    if not value:
        raise OAuthConfigError(f"{name} is not configured.")
    return value
