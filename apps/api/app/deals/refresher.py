"""Deals refresher (invoked by app.scheduled.tick, the single hourly cron).

Fills the cached_round_trips deals cache from Travelpayouts city-directions, one
call per origin airport, so user searches read from our database instead of
calling the provider live. Cheap by design: ~N origin calls per run, not a full
route matrix. Runs on a schedule (Railway cron) and on demand via the CLI.
"""

import logging
from datetime import date

from app.data.flight_places import is_flightable_place
from app.database import SessionLocal
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.cached_deals_repository import DEFAULT_TTL_HOURS, CachedDealsRepository
from app.providers.errors import ProviderError
from app.providers.travelpayouts import TravelpayoutsAviasalesProvider

logger = logging.getLogger(__name__)


def valid_discovery_fares(fares):
    return [
        fare
        for fare in fares
        if fare.origin.upper() != fare.destination.upper()
        and fare.price > 0
        and _valid_date(fare.departureDate)
        and (fare.returnDate is None or _valid_date(fare.returnDate))
        and len(fare.currency) == 3
        and fare.currency.isalpha()
        and is_flightable_place(fare.destination)
    ]


def _valid_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


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

        raw_fetched = 0
        valid_global = 0
        invalid = 0
        upserted = 0
        warnings: list[str] = []
        for origin in origins:
            try:
                fares = provider.discover_round_trips([origin])
            except ProviderError as exc:
                warnings.append(f"{origin}: {exc}")
                continue
            raw_fetched += len(fares)
            valid = valid_discovery_fares(fares)
            valid_global += len(valid)
            invalid += len(fares) - len(valid)
            upserted += deals_repo.upsert_deals(valid, ttl_hours=ttl_hours)

        pruned = deals_repo.prune_stale(ttl_hours=ttl_hours)
        summary = {
            "origins": len(origins),
            "fetched": valid_global,
            "rawFetched": raw_fetched,
            "validGlobal": valid_global,
            "invalidOrUnknown": invalid,
            "upserted": upserted,
            "pruned": pruned,
            "warnings": warnings,
        }
        logger.info(
            "deals_refresh origins=%s raw=%s valid_global=%s invalid=%s upserted=%s pruned=%s warnings=%s",
            summary["origins"], raw_fetched, valid_global, invalid, upserted, pruned, len(warnings),
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
