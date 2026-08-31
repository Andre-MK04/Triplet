"""A ceiling on language-model calls for the whole service, per day.

Per-user quotas stop one account spending too much. They do nothing about a
retry loop, a scripted abuser spread over many addresses, or a bug that calls the
model in a loop — any of which can run up a bill against a small application
overnight. This is the backstop for that.

It is a safety limit, not accounting: an approximate count that fails open on
its own errors, because a broken counter must not take search down. When the
ceiling is reached Triplet keeps working and falls back to the rule-based
parser, so the effect is degraded understanding rather than a dead search box.
"""

from __future__ import annotations

import logging
from datetime import date

from app.config import settings
from app.security.limiter import _get_backend, _InMemoryBackend

logger = logging.getLogger(__name__)

_local_counts: dict[str, int] = {}


def _today_key() -> str:
    return f"triplet:ai:daily:{date.today().isoformat()}"


def consume_ai_call() -> bool:
    """Record one model call. False when the daily ceiling is already reached.

    Callers treat False as "use the rule-based path", never as an error.
    """
    limit = settings.ai_daily_request_limit
    if limit <= 0:
        return True

    key = _today_key()
    backend = _get_backend()
    if isinstance(backend, _InMemoryBackend):
        used = _local_counts.get(key, 0) + 1
        _local_counts.clear()
        _local_counts[key] = used
    else:
        try:
            used = backend._redis.incr(key)
            if used == 1:
                backend._redis.expire(key, 60 * 60 * 36)
        except Exception:
            logger.exception("ai_budget_backend_unavailable")
            return True

    if used > limit:
        logger.warning("ai_daily_budget_reached used=%s limit=%s", used, limit)
        return False
    return True


def ai_calls_today() -> int:
    key = _today_key()
    backend = _get_backend()
    if isinstance(backend, _InMemoryBackend):
        return _local_counts.get(key, 0)
    try:
        return int(backend._redis.get(key) or 0)
    except Exception:
        return 0


def reset_ai_budget() -> None:
    """For tests and local development only."""
    _local_counts.clear()
    backend = _get_backend()
    if not isinstance(backend, _InMemoryBackend):
        try:
            backend._redis.delete(_today_key())
        except Exception:
            logger.exception("ai_budget_reset_failed")
