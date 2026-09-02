"""What must never reach a log line.

Triplet logs are read by people and, where a collector is configured, shipped
off the machine. A token in a log is a token in a place it was never meant to
be, and one that nobody thinks to rotate. So redaction is applied centrally to
every structured field rather than trusted to each call site — a call site can
forget, and the one that forgets is the one that logs the reset token.
"""

from __future__ import annotations

import re
from typing import Any

#: Field names whose value is never safe to record, matched case-insensitively
#: on a substring so `resetToken`, `reset_token` and `RESET_TOKEN` all match.
SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "credential",
    "card",
    "cvv",
    "iban",
    "session",
)

REDACTED = "[redacted]"

#: Things that look like credentials wherever they appear in free text, so a
#: message that interpolated one is caught even though no field was named.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Bearer / Basic authorization values.
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._\-+/=]{8,}", re.I), r"\1 " + REDACTED),
    # JWTs, which appear in cookies and Authorization headers alike.
    (re.compile(r"\beyJ[A-Za-z0-9._\-]{10,}"), REDACTED),
    # Provider keys with recognisable prefixes. Underscores are part of the
    # key body (sk_live_…, sk_test_…), so they must be inside the character
    # class or only the segment before the second underscore is matched.
    (re.compile(r"\b(?:sk|pk|rk)_[A-Za-z0-9_]{8,}"), REDACTED),
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{12,}"), REDACTED),
    (re.compile(r"\bwhsec_[A-Za-z0-9_]{8,}"), REDACTED),
    # A query string carrying a token, which is how manage and unsubscribe
    # links are shaped.
    (re.compile(r"([?&](?:token|reset_token|verification_token)=)[^&\s]+", re.I), r"\1" + REDACTED),
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_text(value: str) -> str:
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def redact(value: Any, _depth: int = 0) -> Any:
    """Return a copy safe to write down.

    Recurses into dicts and sequences, because a token is just as exposed
    nested three levels inside a payload as it is at the top.
    """
    if _depth > 6:
        return "[too deep]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive_key(str(key)) else redact(item, _depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact(item, _depth + 1) for item in value]
    return value
