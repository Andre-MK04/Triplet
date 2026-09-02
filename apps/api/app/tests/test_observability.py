"""Structured logs, and what may never appear in one.

Logs are read by people and, where a collector is configured, shipped off the
machine. A token in a log is a token somewhere it was never meant to be and
that nobody thinks to rotate — so redaction is tested as a security control,
not a nicety.
"""

import json
import logging

import pytest

from app.observability import events
from app.observability.context import current_request_id, set_request_id
from app.observability.logging import MAX_STACK_CHARS, HumanFormatter, JsonFormatter
from app.observability.redaction import REDACTED, redact, redact_text


def record(message: str = "test", **extra) -> logging.LogRecord:
    rec = logging.LogRecord("triplet.test", logging.INFO, __file__, 1, message, (), None)
    for key, value in extra.items():
        setattr(rec, key, value)
    return rec


def formatted(message: str = "test", **extra) -> dict:
    return json.loads(JsonFormatter().format(record(message, **extra)))


# --- Nothing secret is ever written ----------------------------------------

@pytest.mark.parametrize(
    "field",
    [
        "password",
        "newPassword",
        "token",
        "reset_token",
        "verificationToken",
        "manage_token_hash",
        "authorization",
        "cookie",
        "api_key",
        "apiKey",
        "stripe_secret",
        "sessionId",
        "card_number",
    ],
)
def test_a_sensitive_field_is_never_written(field):
    assert formatted(**{field: "super-secret-value"})[field] == REDACTED


def test_secrets_nested_in_a_payload_are_redacted_too():
    """A token is just as exposed three levels down as at the top."""
    out = formatted(payload={"user": {"email": "a@b.com", "reset_token": "abc123"}})

    assert out["payload"]["user"]["reset_token"] == REDACTED
    # Ordinary data is untouched, or the logs stop being useful.
    assert out["payload"]["user"]["email"] == "a@b.com"


def test_credentials_are_caught_in_free_text_even_when_no_field_is_named():
    """The call site that forgets is the one that interpolates a token into a
    message, so the message is scanned as well as the fields."""
    assert "eyJhbGci" not in redact_text("auth failed for eyJhbGciOiJIUzI1NiJ9.abcdefghijkl")
    assert REDACTED in redact_text("Authorization: Bearer abcdefghijklmnop")


@pytest.mark.parametrize(
    "secret",
    ["sk_live_ABCDEFGH1234", "sk_test_51ABCdef", "whsec_ABCdef123456", "sk-proj-abcdefghijklmno"],
)
def test_provider_keys_are_caught_by_shape(secret):
    """Field names cannot be relied on: a key pasted into a message has none."""
    assert secret not in redact_text(f"provider rejected {secret}")


def test_a_token_in_a_manage_link_is_redacted():
    """Watch manage and unsubscribe links carry a bearer token in the query."""
    link = "https://triplet.example/alerts/abc?token=SECRETVALUE123&x=1"

    out = redact_text(link)

    assert "SECRETVALUE123" not in out
    assert "x=1" in out


def test_ordinary_values_survive():
    out = formatted(tripCount=12, provider="travelpayouts", durationMs=340)

    assert out["tripCount"] == 12
    assert out["provider"] == "travelpayouts"


def test_redaction_does_not_recurse_forever():
    payload = {}
    node = payload
    for _ in range(30):
        node["next"] = {}
        node = node["next"]

    assert redact(payload) is not None


# --- The shape of a log line -----------------------------------------------

def test_every_line_is_one_json_object():
    out = formatted("something happened", event="test.event")

    assert out["level"] == "info"
    assert out["message"] == "something happened"
    assert out["event"] == "test.event"
    assert out["ts"]


def test_a_line_carries_the_request_that_produced_it():
    """Without this a provider failure cannot be tied to the search that
    caused it."""
    set_request_id("req-abc123")
    try:
        assert formatted()["requestId"] == "req-abc123"
    finally:
        set_request_id(None)


def test_a_line_outside_a_request_simply_has_none():
    set_request_id(None)

    assert "requestId" not in formatted()


def test_an_exception_is_recorded_by_type_and_message():
    try:
        raise ValueError("provider rejected sk_live_ABCDEFGH1234")
    except ValueError:
        import sys

        rec = record("failed")
        rec.exc_info = sys.exc_info()
        out = json.loads(JsonFormatter().format(rec))

    assert out["error"]["type"] == "ValueError"
    # Redacted here too: an exception message is a common place for a secret
    # to escape.
    assert "sk_live" not in out["error"]["message"]


def _raised_record(message: str = "failed"):
    """A record carrying a real exception, raised through a named helper."""
    import sys

    def inner():
        raise ValueError("provider rejected sk_live_ABCDEFGH1234")

    try:
        inner()
    except ValueError:
        rec = record(message)
        rec.exc_info = sys.exc_info()
        return rec
    raise AssertionError("unreachable")


def test_the_traceback_is_shipped_so_a_500_can_be_located():
    """Without a stack, a production 500 gave a type and nothing to act on.

    This was a real gap: the traceback was omitted on the grounds that Sentry
    would capture it, but Sentry is optional and off by default.
    """
    out = json.loads(JsonFormatter().format(_raised_record()))

    stack = out["error"]["stack"]
    assert "Traceback" in stack
    # The frame that actually raised must be identifiable.
    assert "inner" in stack


def test_a_secret_inside_a_traceback_is_redacted_like_anything_else():
    out = json.loads(JsonFormatter().format(_raised_record()))

    assert "sk_live_ABCDEFGH1234" not in out["error"]["stack"]


def test_a_runaway_traceback_cannot_dominate_the_log():
    rec = _raised_record()
    rec.exc_info = (
        rec.exc_info[0],
        rec.exc_info[1],
        rec.exc_info[2],
    )
    # Stand in for a deeply recursive failure by inflating the message.
    rec.exc_info[1].args = ("x" * (MAX_STACK_CHARS * 3),)

    stack = json.loads(JsonFormatter().format(rec))["error"]["stack"]

    assert len(stack) < MAX_STACK_CHARS * 2
    assert stack.startswith("…truncated…")


def test_local_logs_show_the_traceback_too():
    """The readable formatter is what a developer stares at during a crash."""
    line = HumanFormatter().format(_raised_record())

    assert "Traceback" in line
    assert "inner" in line
    assert "sk_live_ABCDEFGH1234" not in line


def test_an_ordinary_line_carries_no_stack():
    assert "stack" not in json.loads(JsonFormatter().format(record("fine")))
    assert "Traceback" not in HumanFormatter().format(record("fine"))


# --- Events say something about the product --------------------------------

def test_a_search_event_reports_what_matters(caplog):
    with caplog.at_level(logging.INFO, logger="triplet.events"):
        events.search_completed(
            trip_count=0, duration_ms=120, provider="travelpayouts",
            cached=True, stale_fares=3, origins=6,
        )

    rec = caplog.records[-1]
    assert rec.event == "search.completed"
    assert rec.zeroResults is True
    assert rec.staleFares == 3


def test_the_ai_event_never_carries_the_prompt():
    """A travel request is personal, and none of the operational questions —
    cost, latency, fallback rate — need its content."""
    import inspect

    source = inspect.getsource(events.ai_call)

    for forbidden in ("prompt", "message", "content", "query"):
        assert forbidden not in source.split('"""')[0] + source.split('"""')[-1]


def test_timing_records_a_failure_and_re_raises(caplog):
    with caplog.at_level(logging.WARNING, logger="triplet.events"):
        with pytest.raises(RuntimeError):
            with events.timed("test.block", thing="x"):
                raise RuntimeError("boom")

    rec = caplog.records[-1]
    assert rec.outcome == "error"
    assert rec.errorType == "RuntimeError"
    assert isinstance(rec.durationMs, int)


def test_no_event_takes_a_user_identifier():
    """Counts and categories answer the operational questions; an account id
    answers none of them and turns an ops tool into a surveillance one."""
    import inspect

    for name, fn in vars(events).items():
        if not callable(fn) or name.startswith("_") or not hasattr(fn, "__code__"):
            continue
        params = set(inspect.signature(fn).parameters)
        assert not params & {"user_id", "user", "email", "ip"}, f"{name} takes an identifier"
