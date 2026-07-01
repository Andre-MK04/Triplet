import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from uuid import uuid4

import jwt

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


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
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
