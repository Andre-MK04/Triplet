"""One scheduled entry point for all periodic work.

Run hourly by a single Railway cron so we don't operate a service per job:
  1. warm the deals cache (so user searches read from Postgres, not the API),
  2. run due saved-search alerts (they read the freshly-warmed cache),
  3. once a day, prune data past its retention window.

Each underlying job manages its own DB session and never raises past here, so
one failing job can't stop the others. Point the existing cron's start command
at `python -m app.scheduled.tick`.
"""

import logging
import os
from datetime import datetime

from app.alerts.runner import run_due_alerts
from app.deals.refresher import refresh_deals
from app.privacy.retention import run_retention_cleanup

logger = logging.getLogger(__name__)

# Hour (UTC) at which the once-a-day retention cleanup runs on an hourly cron.
RETENTION_HOUR = int(os.getenv("RETENTION_HOUR_UTC", "3"))


def run_tick(now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    summary: dict = {"deals": None, "alertsRun": 0, "retention": None, "errors": []}

    try:
        summary["deals"] = refresh_deals()
    except Exception as exc:  # noqa: BLE001 - one job must not stop the others
        logger.exception("tick_deals_refresh_failed")
        summary["errors"].append(f"deals: {exc}")

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
