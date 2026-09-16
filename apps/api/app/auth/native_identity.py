"""Native identities verified server-side; no trust in a client-supplied email.

Apple uses an expiring, consumed-once nonce plus authorization-code redemption.
Google ID tokens use a strictly configured audience allowlist and Google's JWKS.
Secrets are never returned by a status response or placed in audit payloads.
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import lru_cache
from uuid import uuid4

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.oauth import OAuthConfigError, OAuthProfile, OAuthProviderError, apple_client_secret
from app.config import settings
from app.db.models import NativeAuthChallengeDB, UserOAuthAccountDB


def configured_audiences(provider: str) -> list[str]:
    value = settings.native_google_client_ids if provider == "google" else settings.native_apple_client_ids
    return [v.strip() for v in value.split(",") if v.strip()]


def providers_status() -> dict:
    return {
        "google": bool(configured_audiences("google")),
        "apple": bool(configured_audiences("apple") and settings.apple_oauth_team_id
                      and settings.apple_oauth_key_id and settings.apple_oauth_private_key),
    }


def token_cipher() -> Fernet:
    # Domain-separated key derivation. Rotate APP_SECRET only with a re-encryption plan.
    digest = hashlib.sha256(("native-provider-tokens:v1:" + settings.app_secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def new_challenge(db: Session) -> dict:
    nonce = secrets.token_urlsafe(32)
    row = NativeAuthChallengeDB(id=str(uuid4()), nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(),
                                expires_at=datetime.utcnow() + timedelta(minutes=5))
    db.add(row); db.commit()
    return {"id": row.id, "nonce": nonce}


@lru_cache(maxsize=2)
def _jwks(provider: str):
    url = "https://appleid.apple.com/auth/keys" if provider == "apple" else "https://www.googleapis.com/oauth2/v3/certs"
    return jwt.PyJWKClient(url, timeout=10, lifespan=300)


def verify_token(provider: str, token: str) -> dict:
    audiences = configured_audiences(provider)
    if not audiences or not providers_status().get(provider):
        raise OAuthConfigError("Native sign-in is not configured for this provider.")
    try:
        key = _jwks(provider).get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=audiences,
                            issuer="https://appleid.apple.com" if provider == "apple" else
                            ["https://accounts.google.com", "accounts.google.com"],
                            options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        if not isinstance(claims["sub"], str) or not claims["sub"] or len(claims["sub"]) > 255:
            raise OAuthProviderError("The provider identity is invalid.")
        return claims
    except (jwt.PyJWTError, ValueError) as exc:
        raise OAuthProviderError("Sign-in could not be verified. Please try again.") from exc


async def verified_profile(db: Session, provider: str, payload) -> tuple[OAuthProfile, str | None, str | None]:
    if provider not in {"google", "apple"}:
        raise OAuthConfigError("Unsupported identity provider.")
    claims = await run_in_threadpool(verify_token, provider, payload.idToken)
    encrypted_refresh = None
    client_id = None
    if provider == "apple":
        challenge = db.get(NativeAuthChallengeDB, payload.challengeId) if payload.challengeId else None
        if not challenge or challenge.expires_at <= datetime.utcnow() or challenge.consumed_at:
            raise OAuthProviderError("This sign-in request has expired. Please try again.")
        if not isinstance(claims.get("nonce"), str) or not secrets.compare_digest(challenge.nonce_hash, claims["nonce"]):
            raise OAuthProviderError("The sign-in nonce does not match.")
        if not payload.authorizationCode:
            raise OAuthProviderError("Apple authorization is missing.")
        client_id = claims["aud"]
        if not isinstance(client_id, str):
            raise OAuthProviderError("Apple returned an invalid client identity.")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://appleid.apple.com/auth/token", data={
                "client_id": client_id, "client_secret": apple_client_secret(client_id),
                "code": payload.authorizationCode, "grant_type": "authorization_code",
            })
        if response.status_code != 200:
            raise OAuthProviderError("Apple authorization could not be completed.")
        try:
            body = response.json()
        except ValueError as exc:
            raise OAuthProviderError("Apple authorization could not be completed. Please try again.") from exc
        if not isinstance(body, dict) or not isinstance(body.get("refresh_token"), str) or not body["refresh_token"] or len(body["refresh_token"]) > 16384:
            raise OAuthProviderError("Apple authorization returned an invalid response. Please try again.")
        redeemed = await run_in_threadpool(verify_token, "apple", body.get("id_token", ""))
        if redeemed["sub"] != claims["sub"] or redeemed["aud"] != client_id or not body.get("refresh_token"):
            raise OAuthProviderError("Apple authorization does not match this identity.")
        claimed = db.execute(update(NativeAuthChallengeDB).where(
            NativeAuthChallengeDB.id == challenge.id, NativeAuthChallengeDB.consumed_at.is_(None),
            NativeAuthChallengeDB.expires_at > datetime.utcnow()).values(consumed_at=datetime.utcnow()))
        if claimed.rowcount != 1:
            raise OAuthProviderError("This sign-in request has already been used.")
        encrypted_refresh = token_cipher().encrypt(body["refresh_token"].encode()).decode()
    email = claims.get("email")
    verified = claims.get("email_verified") is True or (provider == "apple" and claims.get("email_verified") == "true")
    if provider == "apple" and not email:
        account = db.scalar(select(UserOAuthAccountDB).where(UserOAuthAccountDB.provider == "apple",
                              UserOAuthAccountDB.provider_user_id == claims["sub"]))
        if account and account.email:
            email = account.email
            verified = True  # Existing subject was verified during its original linkage.
    if not isinstance(email, str) or len(email) > 320 or "@" not in email or not verified:
        raise OAuthProviderError("A verified provider email is required to continue.")
    # Google is authoritative for Gmail / hosted-domain addresses only. Avoid
    # automatic linking by a stale third-party address controlled outside Google.
    if provider == "google" and not email.lower().endswith("@gmail.com") and not claims.get("hd"):
        existing = db.scalar(select(UserOAuthAccountDB).where(UserOAuthAccountDB.provider == "google",
                                 UserOAuthAccountDB.provider_user_id == claims["sub"]))
        from app.db.models import UserDB
        user = db.scalar(select(UserDB).where(UserDB.email == email.strip().lower()))
        if user and not existing:
            raise OAuthProviderError("Sign in with your password first for this email address.")
    name = claims.get("name")
    return OAuthProfile(provider, claims["sub"], email.strip().lower(), True,
                        name[:160] if isinstance(name, str) else None), encrypted_refresh, client_id


def revoke_native_apple_accounts(db: Session, user_id: str) -> None:
    rows = db.scalars(select(UserOAuthAccountDB).where(UserOAuthAccountDB.user_id == user_id,
                      UserOAuthAccountDB.provider == "apple", UserOAuthAccountDB.encrypted_refresh_token.is_not(None))).all()
    for row in rows:
        try:
            token = token_cipher().decrypt(row.encrypted_refresh_token.encode()).decode()
            response = httpx.post("https://appleid.apple.com/auth/revoke", timeout=15, data={
                "client_id": row.native_client_id, "client_secret": apple_client_secret(row.native_client_id),
                "token": token, "token_type_hint": "refresh_token",
            })
            if response.status_code != 200: raise OAuthProviderError("Apple revocation is temporarily unavailable.")
        except (httpx.HTTPError, ValueError, InvalidToken) as exc:
            raise OAuthProviderError("Apple revocation is temporarily unavailable.") from exc
