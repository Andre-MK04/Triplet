"""What Triplet remembers about a fare it was shown.

An observation records one fact: *at about this time, our flight-data source
returned this price for this itinerary*. It does not claim the fare was
bookable, then or now. That distinction is the whole point of the table — it is
a record of the market as our provider reported it, not an inventory.

Deliberately provider-agnostic. Travelpayouts is a value in the ``provider``
column, not a concept baked into the schema, so a future live-fare source can
write here too and be told apart by ``kind`` rather than by a new table.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

# What kind of evidence this is. Statistics use provider observations only;
# composite estimates are Triplet's own arithmetic and would poison a baseline
# built to answer "what does this route normally cost?".
ObservationKind = Literal["cached_provider", "live_provider", "composite_estimate"]
TripShape = Literal["one_way", "return"]

# Anything outside this is a corrupted feed row rather than a fare.
MIN_SANE_PRICE = 1.0
MAX_SANE_PRICE = 25_000.0


@dataclass(frozen=True)
class FareObservation:
    origin: str
    destination: str
    departure_date: date
    price: float
    currency: str
    provider: str
    trip_type: TripShape = "one_way"
    return_date: date | None = None
    #: When the PROVIDER says it found the price. Never invented.
    found_at: datetime | None = None
    #: When Triplet received it. Always known.
    observed_at: datetime | None = None
    kind: ObservationKind = "cached_provider"
    stops: int | None = None
    airline: str | None = None
    confidence: str = "indicative"
    link_available: bool = False

    @property
    def nights(self) -> int | None:
        if self.trip_type != "return" or not self.return_date:
            return None
        return (self.return_date - self.departure_date).days

    def is_valid(self) -> bool:
        """Whether this is worth remembering.

        Composite estimates are excluded here rather than filtered later: a sum
        Triplet computed is not something the provider observed, and letting one
        into the table would quietly corrupt every statistic drawn from it.
        """
        if self.kind == "composite_estimate":
            return False
        if not (MIN_SANE_PRICE <= self.price <= MAX_SANE_PRICE):
            return False
        if self.price != self.price:  # NaN
            return False
        if len(self.origin) < 3 or len(self.destination) < 3:
            return False
        if self.origin.upper() == self.destination.upper():
            return False
        if len(self.currency) != 3 or not self.currency.isalpha():
            return False
        if self.return_date and self.return_date < self.departure_date:
            return False
        nights = self.nights
        if nights is not None and nights > 365:
            return False
        return True

    def identity(self) -> str:
        """A stable key for "this price event", so re-reads do not multiply it.

        Five hundred people opening the same cached fare is one piece of market
        evidence, not five hundred. The provider's own ``found_at`` is what makes
        that determinable — with it, the same event hashes identically however
        often we retrieve it. Without it we fall back to an hour bucket, which is
        conservative: it can merge two genuinely distinct events in one hour, and
        that is the safer error than inflating the sample.
        """
        when = (
            self.found_at.replace(microsecond=0).isoformat()
            if self.found_at
            else (self.observed_at or datetime.utcnow()).strftime("%Y-%m-%dT%H")
        )
        key = "|".join(
            [
                self.provider,
                self.kind,
                self.trip_type,
                self.origin.upper(),
                self.destination.upper(),
                self.departure_date.isoformat(),
                self.return_date.isoformat() if self.return_date else "-",
                f"{self.price:.2f}",
                self.currency.upper(),
                when,
            ]
        )
        return hashlib.sha256(key.encode()).hexdigest()
