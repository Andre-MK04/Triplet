"""Structured logs, so what Triplet does can be measured rather than guessed.

Provider-neutral by design: JSON on stdout, which every hosting platform and
log collector already understands, and which OpenTelemetry or Sentry can be
layered onto later without changing a single call site. Nothing here requires a
vendor or a subscription.

Human-readable lines stay the default for local work — JSON is for somewhere
that ships logs, and reading it by eye during development helps nobody.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

from app.observability.context import current_request_id
from app.observability.redaction import redact, redact_text

#: Fields the standard library puts on every record. Anything else a caller
#: attached is domain data and travels into the payload.
_STANDARD = frozenset(
    """args asctime created exc_info exc_text filename funcName levelname levelno
    lineno module msecs message msg name pathname process processName relativeCreated
    stack_info thread threadName taskName""".split()
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, redacted before it is written."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }

        request_id = current_request_id()
        if request_id:
            payload["requestId"] = request_id

        extras = {key: value for key, value in record.__dict__.items() if key not in _STANDARD}
        if extras:
            payload.update(redact(extras))

        if record.exc_info:
            # The type and message, not the traceback: a traceback in a log
            # aggregator is noise, and Sentry captures it properly when enabled.
            exc_type, exc_value, _ = record.exc_info
            payload["error"] = {
                "type": getattr(exc_type, "__name__", str(exc_type)),
                "message": redact_text(str(exc_value)),
            }

        return json.dumps(payload, default=str)


class HumanFormatter(logging.Formatter):
    """Readable lines for local work, redacted just the same."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<8} {record.name} {redact_text(record.getMessage())}"
        extras = {key: value for key, value in record.__dict__.items() if key not in _STANDARD}
        if extras:
            base += " " + json.dumps(redact(extras), default=str)
        return base


def configure_logging() -> None:
    """Install the formatter once, at startup.

    Structured output is chosen by LOG_FORMAT, defaulting to JSON in production
    and readable lines elsewhere, so a deployment gets parseable logs without
    anyone remembering to ask for them.
    """
    from app.config import settings

    fmt = (os.getenv("LOG_FORMAT") or "").strip().lower()
    if not fmt:
        fmt = "json" if settings.app_env in {"production", "prod"} else "human"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else HumanFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO))

    # uvicorn installs its own handlers; let them fall through to ours so
    # request lines and application lines share one format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
