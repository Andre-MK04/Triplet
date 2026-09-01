import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import settings

ACCESS_COOKIE_NAME = "triplet_access_token"
REFRESH_COOKIE_NAME = "triplet_refresh_token"
PASSWORD_ITERATIONS = 260_000
UNUSABLE_PASSWORD_PREFIX = "oauth_unusable$"


def unusable_password_hash() -> str:
    return f"{UNUSABLE_PASSWORD_PREFIX}{secrets.token_urlsafe(32)}"


def validate_password_strength(password: str, email: str | None = None) -> str | None:
    if len(password) < settings.auth_password_min_length:
        return f"Password must be at least {settings.auth_password_min_length} characters."
    checks = (
        (any(char.islower() for char in password), "one lowercase letter"),
        (any(char.isupper() for char in password), "one uppercase letter"),
        (any(char.isdigit() for char in password), "one number"),
        (any(not char.isalnum() for char in password), "one symbol"),
    )
    missing = [label for passed, label in checks if not passed]
    if missing:
        return "Password must include " + ", ".join(missing) + "."
    if email:
        local_part = email.split("@", 1)[0].lower()
        if local_part and local_part in password.lower():
            return "Password must not contain your email name."
    return None


# Argon2id is the current default. PBKDF2-SHA256 hashes predate it and are still
# accepted at login, then quietly upgraded — see needs_rehash. Nothing here is
# hand-rolled: argon2-cffi is the reference binding for the reference
# implementation, and the parameters below are its maintained defaults.
_argon2 = PasswordHasher()


def hash_password(password: str) -> str:
    return _argon2.hash(password)


def _verify_pbkdf2(password: str, password_hash: str) -> bool:
    """Check a legacy hash. Kept so existing users can still log in."""
    try:
        algorithm, iterations, raw_salt, raw_digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(raw_salt)
        expected = base64.b64decode(raw_digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith(UNUSABLE_PASSWORD_PREFIX):
        # OAuth-only account: there is no password to be right about.
        return False
    if password_hash.startswith("$argon2"):
        try:
            return _argon2.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            return False
    return _verify_pbkdf2(password, password_hash)


def needs_rehash(password_hash: str | None) -> bool:
    """Whether this hash should be replaced after a successful login.

    True for every legacy PBKDF2 hash, and for Argon2 hashes made with
    parameters weaker than the current ones — so raising the cost later
    upgrades the estate on its own, without a migration or a password reset.
    """
    if not password_hash or password_hash.startswith(UNUSABLE_PASSWORD_PREFIX):
        return False
    if not password_hash.startswith("$argon2"):
        return True
    try:
        return _argon2.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_access_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + settings.auth_access_token_expire_minutes * 60,
        "typ": "access",
    }
    return jwt.encode(payload, settings.app_secret, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.app_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    return payload.get("sub")


def create_refresh_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(days=settings.auth_refresh_token_expire_days)
    return raw, hash_token(raw), expires_at


def create_reset_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    return raw, hash_token(raw), expires_at


def hash_token(token: str) -> str:
    return hmac.new(settings.app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def verify_token(raw_token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(raw_token), token_hash)


def new_uuid() -> str:
    return str(uuid4())
