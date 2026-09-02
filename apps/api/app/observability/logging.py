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
import traceback
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


#: Enough frames to identify the failure without letting one crash dominate a
#: log budget. The tail is kept rather than the head: the innermost frames and
#: the exception line are what name the faulty code.
MAX_STACK_CHARS = 4000


def _formatted_stack(exc_info) -> str:
    """The traceback as text, redacted and bounded.

    Redacted for the same reason every other field is: an exception message or a
    local variable rendered into a frame can carry a token or an email address,
    and a traceback is not exempt from that just because it is diagnostic.
    """
    text = "".join(traceback.format_exception(*exc_info)).rstrip()
    if len(text) > MAX_STACK_CHARS:
        text = "…truncated…\n" + text[-MAX_STACK_CHARS:]
    return redact_text(text)


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
            exc_type, exc_value, _ = record.exc_info
            payload["error"] = {
                "type": getattr(exc_type, "__name__", str(exc_type)),
                "message": redact_text(str(exc_value)),
                # The traceback ships too. An earlier version left it out on the
                # grounds that Sentry would capture it — but Sentry is optional
                # and unconfigured by default, so that reasoning only held for
                # deployments that had already solved the problem. Without a DSN
                # a 500 left the type and message and nothing else, which is not
                # enough to find the line that raised it.
                "stack": _formatted_stack(record.exc_info),
            }

        return json.dumps(payload, default=str)


class HumanFormatter(logging.Formatter):
    """Readable lines for local work, redacted just the same."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<8} {record.name} {redact_text(record.getMessage())}"
        extras = {key: value for key, value in record.__dict__.items() if key not in _STANDARD}
        if extras:
            base += " " + json.dumps(redact(extras), default=str)
        if record.exc_info:
            # Local work is exactly where a traceback earns its space. Without
            # this, a crash printed one unhelpful line and the developer went
            # looking for a stack trace that was never written anywhere.
            base += "\n" + _formatted_stack(record.exc_info)
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
