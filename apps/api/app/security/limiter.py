"""Shared rate limiting across every process that serves Triplet.

The previous limiter counted attempts in a module-level dict, which meant each
worker enforced its own private budget: two workers doubled every limit, a
restart cleared them, and horizontal scaling removed them almost entirely. That
is adequate for local development and close to useless as production protection
on endpoints that spend money.

Limits are expressed as named categories rather than per-route numbers, so a new
endpoint is protected by declaring what kind of work it does. An endpoint that
calls a language model is `AI` wherever it lives, and cannot accidentally be
cheaper to abuse than its neighbour.

Backend selection is by configuration, never silent: with REDIS_URL set the
counters are shared, without it they are per-process and the application says so
at startup, loudly, every time. See `validate_for_production`.

Missing Redis is a warning rather than a startup failure. A single-worker
deployment is genuinely protected by per-process counters, and refusing to boot
over an unset variable trades a small, conditional weakness for a total outage —
a bad exchange. Deployments that must never run unshared set
RATE_LIMIT_REQUIRE_SHARED=true and get the hard failure instead.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitCategory(str, Enum):
    """What kind of work an endpoint does, which is what its budget follows."""

    #: Metadata and autocomplete. Cheap, but not free to flood.
    CHEAP = "cheap"
    #: Flight searches. Each one can reach a paid provider.
    SEARCH = "search"
    #: Anything that reaches a language model.
    AI = "ai"
    #: Credentials and account recovery. Tight, to blunt guessing.
    AUTH = "auth"
    #: Creating or running price watches, which can send email.
    ALERTS = "alerts"


@dataclass(frozen=True)
class Budget:
    max_attempts: int
    window_seconds: int


def budget_for(category: RateLimitCategory) -> Budget:
    window = settings.api_rate_limit_window_seconds
    if category is RateLimitCategory.CHEAP:
        return Budget(settings.rate_limit_cheap_per_window, window)
    if category is RateLimitCategory.SEARCH:
        return Budget(settings.trips_search_rate_limit_max_attempts, window)
    if category is RateLimitCategory.AI:
        return Budget(settings.ai_search_rate_limit_max_attempts, window)
    if category is RateLimitCategory.ALERTS:
        return Budget(settings.rate_limit_alerts_per_window, window)
    return Budget(settings.auth_rate_limit_max_attempts, settings.auth_rate_limit_window_seconds)


class RateLimitExceeded(Exception):
    """Raised when a caller is over budget. Carries the wait the caller should honour."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__(f"Rate limit exceeded; retry in {self.retry_after_seconds}s")


class _InMemoryBackend:
    """Per-process counters. Correct for a single worker, and only that."""

    name = "in-memory"

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, budget: Budget, now: float) -> int:
        with self._lock:
            hits = self._hits[key]
            cutoff = now - budget.window_seconds
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= budget.max_attempts:
                return int(hits[0] + budget.window_seconds - now) + 1
            hits.append(now)
            return 0

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


class _RedisBackend:
    """Counters shared by every process, in fixed windows.

    A fixed window rather than a sliding log: it is one INCR plus one EXPIRE, it
    cannot grow without bound, and its worst case — twice the budget across a
    window boundary — is a price worth paying for an operation on the request path.
    """

    name = "redis"

    def __init__(self, client) -> None:
        self._redis = client

    def hit(self, key: str, budget: Budget, now: float) -> int:
        window_start = int(now // budget.window_seconds) * budget.window_seconds
        slot = f"triplet:rl:{key}:{window_start}"
        try:
            used = self._redis.incr(slot)
            if used == 1:
                self._redis.expire(slot, budget.window_seconds + 1)
        except Exception:
            # A limiter outage must not take the API down with it. Log loudly and
            # let the request through: availability beats a perfect count, and
            # the failure is visible rather than silent.
            logger.exception("rate_limit_backend_unavailable key=%s", key)
            return 0
        if used > budget.max_attempts:
            return int(window_start + budget.window_seconds - now) + 1
        return 0

    def clear(self) -> None:
        try:
            for key in self._redis.scan_iter("triplet:rl:*"):
                self._redis.delete(key)
        except Exception:
            logger.exception("rate_limit_backend_clear_failed")


_backend = None


def _get_backend():
    global _backend
    if _backend is not None:
        return _backend
    url = settings.redis_url
    if url:
        try:
            import redis  # imported lazily so local dev needs no redis package

            _backend = _RedisBackend(redis.Redis.from_url(url, decode_responses=True))
            logger.info("rate_limit_backend=redis")
            return _backend
        except Exception:
            logger.exception("rate_limit_redis_unavailable falling_back=in-memory")
    _backend = _InMemoryBackend()
    logger.info("rate_limit_backend=in-memory")
    return _backend


def limiter_backend_name() -> str:
    return _get_backend().name


def reset_rate_limits() -> None:
    """Clear all counters. For tests and local development only."""
    _get_backend().clear()


def identity_for(request, user_id: str | None) -> str:
    """Who is being limited.

    An authenticated caller is limited as themselves, so rotating IPs does not
    buy extra budget; everyone else is limited by client address. The proxy
    header is trusted only when the deployment says it sits behind one, because
    an unproxied service would otherwise let a caller pick their own identity.
    """
    if user_id:
        return f"user:{user_id}"
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
    client = getattr(request, "client", None)
    return f"ip:{client.host if client else 'unknown'}"


def check_rate_limit(
    category: RateLimitCategory,
    request,
    user_id: str | None = None,
    cost: int = 1,
) -> None:
    """Charge this request against its category budget.

    ``cost`` lets one call count as several, for endpoints that do markedly more
    work than others in the same category.
    """
    budget = budget_for(category)
    key = f"{category.value}:{identity_for(request, user_id)}"
    backend = _get_backend()
    now = time.time()
    retry_after = 0
    for _ in range(max(1, cost)):
        retry_after = backend.hit(key, budget, now)
        if retry_after:
            break
    if retry_after:
        raise RateLimitExceeded(retry_after)


UNSHARED_LIMITS_WARNING = (
    "REDIS_URL is not set, so rate limits are counted per process. This is adequate "
    "for a single worker on a single instance, and NOT adequate beyond that: every "
    "extra worker or instance multiplies the effective limit. Set REDIS_URL to share "
    "the counters."
)


def check_production_limits() -> str | None:
    """Warn when limits are per-process in production. Never fatal by default.

    Returns the warning to log, or None when the configuration is sound. This
    deliberately does not raise: an unset variable must not crash-loop a running
    service over a weakness that may not even apply to it.
    """
    if settings.app_env not in {"production", "prod"}:
        return None
    if settings.redis_url:
        return None
    return UNSHARED_LIMITS_WARNING


def validate_for_production() -> list[str]:
    """Configuration problems severe enough to refuse to start.

    Only when the deployment has explicitly said it requires shared counters —
    a multi-worker service where per-process limits really are ineffective.
    """
    if settings.rate_limit_require_shared and not settings.redis_url:
        return [
            "RATE_LIMIT_REQUIRE_SHARED is set but REDIS_URL is not. This deployment has "
            "declared that per-process rate limits are not acceptable for it."
        ]
    return []
