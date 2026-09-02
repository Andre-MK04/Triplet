"""The things worth knowing about a running Triplet.

One function per question someone would actually ask, rather than a generic
metric API. The point is that the call sites read as statements about the
product — a search found nothing, a fare was stale, a watch could not be
delivered — so what is measured stays legible as the code changes.

Every event is a structured log line. That is deliberately the lowest common
denominator: it costs nothing, works on any host, and a collector, Sentry or an
OpenTelemetry exporter can be added later without touching a single call site.

Nothing here records who did something. Counts, latencies and categories answer
the operational questions; an account id in a log answers none of them and
turns an ops tool into a surveillance one.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("triplet.events")


@contextmanager
def timed(event: str, **fields):
    """Time a block and emit one event with its duration.

    Emits on failure too, with the exception type, because how long something
    took before it broke is usually the interesting part.
    """
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        logger.warning(
            event,
            extra={
                "event": event,
                "durationMs": round((time.perf_counter() - started) * 1000),
                "outcome": "error",
                "errorType": type(exc).__name__,
                **fields,
            },
        )
        raise
    else:
        logger.info(
            event,
            extra={
                "event": event,
                "durationMs": round((time.perf_counter() - started) * 1000),
                "outcome": "ok",
                **fields,
            },
        )


def _emit(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, event, extra={"event": event, **fields})


# --- Search -----------------------------------------------------------------

def search_completed(
    *,
    trip_count: int,
    duration_ms: int,
    provider: str | None,
    cached: bool,
    stale_fares: int = 0,
    origins: int = 0,
    ai: bool = False,
) -> None:
    """One completed search. Zero results is the number worth watching."""
    _emit(
        "search.completed",
        tripCount=trip_count,
        durationMs=duration_ms,
        provider=provider,
        cachedResultsUsed=cached,
        # What share of what we showed was already old — the quantity behind
        # every freshness claim in the interface.
        staleFares=stale_fares,
        originCount=origins,
        aiAssisted=ai,
        zeroResults=trip_count == 0,
    )


def provider_failed(*, provider: str, reason: str) -> None:
    _emit("search.provider_failed", level=logging.WARNING, provider=provider, reason=reason)


# --- AI ---------------------------------------------------------------------

def ai_call(
    *, provider: str, model: str, duration_ms: int, tool_calls: int = 0, fallback: bool = False
) -> None:
    """A model call. Never the prompt: a travel request is personal, and the
    operational questions are about cost and latency, not content."""
    _emit(
        "ai.call",
        provider=provider,
        model=model,
        durationMs=duration_ms,
        toolCalls=tool_calls,
        fallbackUsed=fallback,
    )


def ai_budget_exhausted(*, used: int, limit: int) -> None:
    _emit("ai.budget_exhausted", level=logging.WARNING, used=used, limit=limit)


def ai_fallback(*, reason: str) -> None:
    """Rule-based parsing stood in for the model."""
    _emit("ai.fallback", level=logging.WARNING, reason=reason)


# --- Pricing ----------------------------------------------------------------

def observations_recorded(*, count: int) -> None:
    _emit("pricing.observations_recorded", count=count)


def price_classified(*, classification: str, sample_count: int, basis: str | None) -> None:
    """A verdict shown to a traveller, with the evidence behind it — so a claim
    can be traced back to how much data supported it."""
    _emit(
        "pricing.classified",
        classification=classification,
        sampleCount=sample_count,
        basis=basis,
    )


# --- What travellers do -----------------------------------------------------

def watch_created(*, anonymous: bool, trigger: str | None, frequency: str) -> None:
    _emit("watch.created", anonymous=anonymous, trigger=trigger, frequency=frequency)


def watch_verified() -> None:
    """An anonymous watch confirmed its address. The other half of the funnel
    that watch.created starts, and the one that says whether the double opt-in
    is costing more watches than it protects."""
    _emit("watch.verified")


def fare_feedback_received(*, response: str, age_bucket: str, fare_kind: str) -> None:
    _emit("fare.feedback", response=response, ageBucket=age_bucket, fareKind=fare_kind)


# --- Alerts -----------------------------------------------------------------

def alert_run(*, status: str, result_count: int, notified: bool) -> None:
    _emit("alert.run", status=status, resultCount=result_count, notified=notified)


def alert_delivery(*, ok: bool, provider: str, reason: str | None = None) -> None:
    _emit(
        "alert.delivery",
        level=logging.INFO if ok else logging.WARNING,
        ok=ok,
        provider=provider,
        reason=reason,
    )


def alert_duplicate_prevented(*, saved_search_id: str) -> None:
    """A second runner was refused the right to send. Worth counting: if this
    is common the scheduler is overlapping more than intended."""
    _emit("alert.duplicate_prevented", savedSearchId=saved_search_id)


# --- Infrastructure ---------------------------------------------------------

def dependency_failed(*, dependency: str, reason: str) -> None:
    """A database, cache or provider Triplet depends on is not answering."""
    _emit("dependency.failed", level=logging.ERROR, dependency=dependency, reason=reason)


def scheduled_job(*, job: str, ok: bool, duration_ms: int, detail: dict | None = None) -> None:
    _emit(
        "job.completed",
        level=logging.INFO if ok else logging.ERROR,
        job=job,
        ok=ok,
        durationMs=duration_ms,
        detail=detail or {},
    )
