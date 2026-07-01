import hmac
import secrets
from hashlib import sha256

from app.config import settings


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hmac.new(settings.app_secret.encode(), token.encode(), sha256).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)
