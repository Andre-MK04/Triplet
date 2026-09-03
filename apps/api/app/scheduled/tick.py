"""One scheduled entry point for all periodic work.

Run hourly by a single Railway cron so we don't operate a service per job:
  1. warm the deals cache (so user searches read from Postgres, not the API),
  2. rebuild the homepage board from that cache (so a page view never searches),
  3. run due saved-search alerts (they read the freshly-warmed cache),
  4. once a day, prune data past its retention window.

Each underlying job manages its own DB session and never raises past here, so
one failing job can't stop the others. Point the existing cron's start command
at `python -m app.scheduled.tick`.
"""

import logging
import os
import time
from datetime import datetime

from app.alerts.email import build_email_provider
from app.alerts.runner import run_due_alerts
from app.config import settings
from app.observability import events
from app.deals.featured import refresh_featured_deals
from app.deals.refresher import refresh_deals
from app.privacy.retention import run_retention_cleanup

logger = logging.getLogger(__name__)

# Hour (UTC) at which the once-a-day retention cleanup runs on an hourly cron.
RETENTION_HOUR = int(os.getenv("RETENTION_HOUR_UTC", "3"))


def _alerts_would_be_delivered(summary: dict) -> bool:
    """Whether it is worth running the alert pass at all.

    This runs in the cron service, which never starts FastAPI — so the
    production configuration guard in `app.main` has never protected it. The
    consequence was specific and bad: with a provider that delivers nothing,
    the alert runner claims each watch's notification slot *before* sending and
    marks it notified afterwards regardless. Every due watch would advance its
    cooldown for an email nobody received, and that deal would never be re-sent
    once the configuration was fixed. Silent, permanent, and invisible in the
    watch history, which would say the alert went out.

    A deployment that has declared it wants real email gets the pass skipped,
    so nothing is spent. Anywhere else it still runs — local work with the
    console provider is how the alert path gets exercised at all — but says
    plainly what it is about to cost.
    """
    provider_delivers = build_email_provider().delivers
    if provider_delivers:
        return True

    if settings.email_require_real_provider:
        message = (
            "alerts skipped: EMAIL_REQUIRE_REAL_PROVIDER is set but the configured provider "
            "delivers no email. Running the pass would burn every due watch's cooldown on "
            "messages nobody receives."
        )
        logger.error("tick_alerts_skipped_no_delivery: %s", message)
        summary["errors"].append(f"alerts: {message}")
        return False

    logger.warning(
        "tick_alerts_no_delivery: the configured email provider delivers nothing, so this pass "
        "will advance each notified watch's cooldown without anyone receiving mail. Set "
        "EMAIL_REQUIRE_REAL_PROVIDER=true on this service to skip the pass instead."
    )
    return True


def run_tick(now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    started = time.perf_counter()
    summary: dict = {
        "deals": None,
        "featuredDeals": None,
        "alertsRun": 0,
        "retention": None,
        "errors": [],
    }

    try:
        summary["deals"] = refresh_deals()
    except Exception as exc:  # noqa: BLE001 - one job must not stop the others
        logger.exception("tick_deals_refresh_failed")
        summary["errors"].append(f"deals: {exc}")

    try:
        # After the fare cache is warm, because the board is built from it.
        summary["featuredDeals"] = refresh_featured_deals()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tick_featured_deals_failed")
        summary["errors"].append(f"featured: {exc}")

    if _alerts_would_be_delivered(summary):
        try:
            summary["alertsRun"] = len(run_due_alerts())
        except Exception as exc:  # noqa: BLE001
            logger.exception("tick_alerts_failed")
            summary["errors"].append(f"alerts: {exc}")

    if now.hour == RETENTION_HOUR:
        try:
            summary["retention"] = run_retention_cleanup()
        except Exception as exc:  # noqa: BLE001
            logger.exception("tick_retention_failed")
            summary["errors"].append(f"retention: {exc}")

    events.scheduled_job(
        job="tick",
        ok=not summary["errors"],
        duration_ms=round((time.perf_counter() - started) * 1000),
        detail={
            "alertsRun": summary["alertsRun"],
            "errors": len(summary["errors"]),
        },
    )
    logger.info(
        "scheduled_tick deals=%s alerts=%s retention=%s errors=%s",
        bool(summary["deals"]), summary["alertsRun"], bool(summary["retention"]), len(summary["errors"]),
    )
    return summary


def main() -> None:
    summary = run_tick()
    deals = summary["deals"] or {}
    print(
        f"Tick done: deals upserted {deals.get('upserted', 0)}, "
        f"alerts run {summary['alertsRun']}, "
        f"retention {'ran' if summary['retention'] else 'skipped'}."
    )
    for err in summary["errors"]:
        print(f"  error: {err}")


if __name__ == "__main__":
    main()
