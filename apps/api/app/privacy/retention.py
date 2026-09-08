"""Scheduled data-retention cleanup (GDPR data-minimisation / storage limitation).

Prunes data past its documented retention window. Windows are conservative and
configurable; anything a user still needs is left untouched. Run on a schedule
(Railway cron) and on demand via the CLI.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete

from app.database import SessionLocal
from app.db.models import AuditEventDB, CachedRoundTripDB, EmailEventDB, TripSuggestionDB

logger = logging.getLogger(__name__)

AUDIT_RETENTION_DAYS = 180  # security logs kept ~6 months, then dropped
CACHED_DEALS_RETENTION_DAYS = 3  # deals cache is short-lived; refresher keeps it warm
EMAIL_EVENT_RETENTION_DAYS = 90  # minimal delivery metadata; suppressions are separate


def run_retention_cleanup() -> dict:
    with SessionLocal() as db:
        return cleanup(db)


def cleanup(db, now: datetime | None = None) -> dict:
    """Prune data past its retention window using the given session (testable)."""
    now = now or datetime.utcnow()
    audit_cutoff = now - timedelta(days=AUDIT_RETENTION_DAYS)
    deals_cutoff = now - timedelta(days=CACHED_DEALS_RETENTION_DAYS)
    email_event_cutoff = now - timedelta(days=EMAIL_EVENT_RETENTION_DAYS)

    audit_deleted = db.execute(
        delete(AuditEventDB).where(AuditEventDB.created_at < audit_cutoff)
    ).rowcount or 0
    deals_deleted = db.execute(
        delete(CachedRoundTripDB).where(CachedRoundTripDB.observed_at < deals_cutoff)
    ).rowcount or 0
    # Expired trip-suggestion links (expires_at set at creation).
    suggestions_deleted = db.execute(
        delete(TripSuggestionDB).where(
            TripSuggestionDB.expires_at.is_not(None),
            TripSuggestionDB.expires_at < now,
        )
    ).rowcount or 0
    email_events_deleted = db.execute(
        delete(EmailEventDB).where(EmailEventDB.received_at < email_event_cutoff)
    ).rowcount or 0
    db.commit()

    summary = {
        "auditDeleted": audit_deleted,
        "cachedDealsDeleted": deals_deleted,
        "expiredSuggestionsDeleted": suggestions_deleted,
        "emailEventsDeleted": email_events_deleted,
    }
    logger.info(
        "retention_cleanup audit=%s deals=%s suggestions=%s email_events=%s",
        audit_deleted, deals_deleted, suggestions_deleted, email_events_deleted,
    )
    return summary


def main() -> None:
    summary = run_retention_cleanup()
    print(
        f"Retention cleanup: {summary['auditDeleted']} audit, "
        f"{summary['cachedDealsDeleted']} cached deals, "
        f"{summary['expiredSuggestionsDeleted']} expired suggestions, "
        f"{summary['emailEventsDeleted']} email events removed."
    )


if __name__ == "__main__":
    main()
