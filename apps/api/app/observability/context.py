"""The request a log line belongs to.

Every response already carries an X-Request-ID, but nothing put it into the
logs, so a line saying a provider failed could not be tied to the search that
provoked it. A context variable carries it to every log record emitted while
handling that request, including from code several layers down that knows
nothing about HTTP.
"""

from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("triplet_request_id", default=None)


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def current_request_id() -> str | None:
    return _request_id.get()
