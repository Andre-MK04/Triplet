"""Scheduled deals refresher.

Fills the cached_round_trips deals cache from Travelpayouts city-directions, one
call per origin airport, so user searches read from our database instead of
calling the provider live. Cheap by design: ~N origin calls per run, not a full
route matrix. Runs on a schedule (Railway cron) and on demand via the CLI.
"""

import logging

from app.data.geography import is_european
from app.database import SessionLocal
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.cached_deals_repository import DEFAULT_TTL_HOURS, CachedDealsRepository
from app.providers.errors import ProviderError
from app.providers.travelpayouts import TravelpayoutsAviasalesProvider

logger = logging.getLogger(__name__)


def refresh_deals(ttl_hours: int = DEFAULT_TTL_HOURS) -> dict:
    """Refresh the deals cache for every origin-candidate airport.

    Returns a summary dict {origins, fetched, upserted, pruned, warnings}.
    Never raises on provider errors — a bad origin is logged and skipped.
    """
    with SessionLocal() as db:
        origins = [
            airport.code for airport in AirportsRepository(db).list_origin_candidates()
        ]
        deals_repo = CachedDealsRepository(db)
        provider = TravelpayoutsAviasalesProvider(db=db)

        fetched = 0
        upserted = 0
        warnings: list[str] = []
        for origin in origins:
            try:
                fares = provider.discover_round_trips([origin])
            except ProviderError as exc:
                warnings.append(f"{origin}: {exc}")
                continue
            european = [fare for fare in fares if is_european(fare.destination)]
            fetched += len(european)
            upserted += deals_repo.upsert_deals(european, ttl_hours=ttl_hours)

        pruned = deals_repo.prune_stale(ttl_hours=ttl_hours)
        summary = {
            "origins": len(origins),
            "fetched": fetched,
            "upserted": upserted,
            "pruned": pruned,
            "warnings": warnings,
        }
        logger.info(
            "deals_refresh origins=%s fetched=%s upserted=%s pruned=%s warnings=%s",
            summary["origins"], fetched, upserted, pruned, len(warnings),
        )
        return summary


def main() -> None:
    summary = refresh_deals()
    print(
        f"Refreshed deals: {summary['origins']} origin(s), fetched {summary['fetched']}, "
        f"upserted {summary['upserted']}, pruned {summary['pruned']}."
    )
    for warning in summary["warnings"]:
        print(f"  warning: {warning}")


if __name__ == "__main__":
    main()
