"""Deals refresher (invoked by app.scheduled.tick, the single hourly cron).

Fills the cached_round_trips deals cache so user searches read from our database
instead of calling the provider live. Two queries per origin: city-directions for
the widest spread of destinations, and the per-month price query for fares inside
the window people actually search — the latter is the one whose rows carry the
provider's own sighting date.

Worth being clear about what this can and cannot do. Travelpayouts serves fares
other travellers recently searched; asking twice a second apart returns the same
fares with the same sighting dates. Running this more often therefore improves
*coverage* — how quickly we notice a route the provider has newly priced — and
not the age of any individual fare, which runs 0-7 days regardless. Cheap by
design: a few calls per origin per run, never a route matrix.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import select

from app.config import settings
from app.data.flight_places import is_flightable_place, is_supported_origin
from app.database import SessionLocal
from app.db.models import SavedSearchDB, UserTravelProfileDB
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.cached_deals_repository import CachedDealsRepository
from app.providers.errors import ProviderError
from app.providers.flight_provider import DateRange
from app.providers.travelpayouts import TravelpayoutsAviasalesProvider

logger = logging.getLogger(__name__)

# How far ahead the hourly warm-up fetches dated fares. One provider request per
# origin per calendar month touched, so this directly sets the hourly API cost.
WARM_HORIZON_DAYS = 75
# Ceiling on provider calls for one warm-up run, so a misconfiguration cannot
# turn the hourly cron into an unbounded spend.
WARM_REQUEST_BUDGET = 400


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


def origins_to_warm(db, limit: int | None = None) -> list[str]:
    """Airports worth keeping a warm cache for.

    The seeded origin candidates plus the airports people actually chose — travel
    profiles and active watches. Onboarding now offers the whole European airport
    directory, so warming only the seeded eight left every other traveller's
    "anywhere" search reading a cache that had nothing for their airport.
    """
    codes: list[str] = [airport.code for airport in AirportsRepository(db).list_origin_candidates()]

    for row_airports in db.scalars(select(UserTravelProfileDB.origin_airports)).all():
        codes.extend(str(code).upper() for code in (row_airports or []))
    for row_airports in db.scalars(
        select(SavedSearchDB.origin_airports).where(SavedSearchDB.is_active.is_(True))
    ).all():
        codes.extend(str(code).upper() for code in (row_airports or []))

    unique = [code for code in dict.fromkeys(codes) if is_supported_origin(code)]
    return unique[: limit or settings.deals_max_warmed_origins]


def refresh_deals(ttl_hours: int | None = None) -> dict:
    """Refresh the deals cache for every origin worth keeping warm.

    Returns a summary dict {origins, fetched, upserted, pruned, warnings}.
    Never raises on provider errors — a bad origin is logged and skipped.
    """
    with SessionLocal() as db:
        origins = origins_to_warm(db)
        deals_repo = CachedDealsRepository(db)
        provider = TravelpayoutsAviasalesProvider(db=db, max_requests=WARM_REQUEST_BUDGET)

        window = DateRange(start=date.today(), end=date.today() + timedelta(days=WARM_HORIZON_DAYS))

        raw_fetched = 0
        valid_global = 0
        invalid = 0
        upserted = 0
        warnings: list[str] = []
        for origin in origins:
            try:
                # city-directions reaches the most destinations; the in-window
                # query is the one that returns fares carrying the provider's own
                # sighting date, so cached "anywhere" results can report an age
                # instead of an unhelpful "unknown".
                fares = provider.discover_round_trips([origin])
                fares += provider.round_trips_in_window([origin], window)
            except ProviderError as exc:
                warnings.append(f"{origin}: {exc}")
                continue
            raw_fetched += len(fares)
            valid = valid_discovery_fares(fares)
            valid_global += len(valid)
            invalid += len(fares) - len(valid)
            upserted += deals_repo.upsert_deals(valid, ttl_hours=ttl_hours)

        pruned = deals_repo.prune_stale()
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
