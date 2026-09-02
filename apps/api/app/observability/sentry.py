"""Optional error reporting.

Entirely opt-in: without SENTRY_DSN nothing is imported, nothing is sent, and
the rest of observability works unchanged. Structured logs are the floor;
Sentry is a convenience on top for anyone who wants tracebacks grouped.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.observability.redaction import redact

logger = logging.getLogger(__name__)


def configure_sentry() -> bool:
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        # Configured but not installed. Say so rather than failing to start:
        # missing error reporting is not a reason to refuse traffic.
        logger.warning("sentry_dsn_set_but_sdk_missing install=sentry-sdk")
        return False

    def scrub(event, _hint):
        # The same redaction the logs get. Sentry has its own scrubbing, but
        # relying on a vendor's default for our own token shapes would be
        # trusting someone else to know what Triplet's secrets look like.
        return redact(event)

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        before_send=scrub,
        # Off unless deliberately enabled: traces cost money and this is meant
        # to work on a free tier.
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    logger.info("sentry_enabled environment=%s", settings.app_env)
    return True
