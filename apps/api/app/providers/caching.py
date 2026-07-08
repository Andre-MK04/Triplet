import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.repositories.flights_repository import FlightsRepository
from app.models import Flight

logger = logging.getLogger(__name__)


def cache_flights(db: Session | None, flights: list[Flight]) -> int:
    """Best-effort cache of provider flights into the flights table.

    Caching is an optimization and price-history feed, never core to returning a
    search. Any database error is rolled back and swallowed so a cache failure can
    never turn a working search into a 503. Returns how many flights were cached.
    """
    if not db or not flights:
        return 0
    try:
        FlightsRepository(db).upsert_flights(flights)
        return len(flights)
    except SQLAlchemyError:
        db.rollback()
        logger.warning("flight_cache_write_failed count=%s", len(flights), exc_info=True)
        return 0
