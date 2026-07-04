from collections.abc import Callable

from fastapi import Request

from app.config import settings
from app.rate_limit import rate_limit


def auth_rate_limit(action: str) -> Callable[[Request], None]:
    return rate_limit(
        action=f"auth:{action}",
        max_attempts=settings.auth_rate_limit_max_attempts,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )
