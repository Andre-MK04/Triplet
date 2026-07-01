import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.config import settings

_attempts: dict[str, deque[float]] = defaultdict(deque)


def auth_rate_limit(action: str) -> Callable[[Request], None]:
    def check(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{action}:{client_ip}"
        now = time.time()
        window_start = now - settings.auth_rate_limit_window_seconds
        attempts = _attempts[key]

        while attempts and attempts[0] < window_start:
            attempts.popleft()

        if len(attempts) >= settings.auth_rate_limit_max_attempts:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

        attempts.append(now)

    return check
