from collections.abc import Callable

from fastapi import Request

from app.security import RateLimitCategory, check_rate_limit


def auth_rate_limit(action: str) -> Callable[[Request], None]:
    """Credential-endpoint limiting, on the shared limiter.

    This used to wrap a per-process counter, which meant login and password
    reset attempts were counted separately by each worker — the endpoints where
    a shared count matters most. The `action` argument is kept because the auth
    routes read well with it, but every credential endpoint now draws on one
    AUTH budget per caller: an attacker gains nothing by spreading attempts
    across signup, login and reset.
    """

    def check(request: Request) -> None:
        check_rate_limit(RateLimitCategory.AUTH, request)

    return check
