import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request


_attempts: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(action: str, max_attempts: int, window_seconds: int) -> Callable[[Request], None]:
    def check(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{action}:{client_ip}"
        now = time.time()
        window_start = now - window_seconds
        attempts = _attempts[key]

        while attempts and attempts[0] < window_start:
            attempts.popleft()

        if len(attempts) >= max_attempts:
            raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

        attempts.append(now)

    return check


def clear_rate_limits() -> None:
    _attempts.clear()
