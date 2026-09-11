import hmac
import secrets
from hashlib import sha256

from app.config import settings


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def stable_action_token(resource_id: str, action: str) -> str:
    """A reproducible bearer HMAC token for links sent after creation.

    Only a hash is stored in the database. A random unsubscribe token therefore
    cannot be recovered when a scheduled alert is built days later. Deriving it
    from the application secret keeps the database free of bearer credentials
    while allowing every email to carry a working opt-out link.
    """
    message = f"farelin:{action}:{resource_id}"
    return hmac.new(settings.app_secret.encode(), message.encode(), sha256).hexdigest()


def hash_token(token: str) -> str:
    return hmac.new(settings.app_secret.encode(), token.encode(), sha256).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)
