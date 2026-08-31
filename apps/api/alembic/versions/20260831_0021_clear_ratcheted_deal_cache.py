"""drop cached deals written while the cache ratcheted to the cheapest price

Until the preceding change, upsert_deals kept a stored price whenever a refresh
returned a dearer one, and refreshed its freshness stamp while doing so. Every
route therefore ratcheted down to the lowest price ever seen and then presented
that as freshly observed — one Vienna-Rome trip quoted EUR 48 against a live
EUR 96. Rows written under that rule cannot be repaired in place, because the
price they hold is not one the provider ever offered at the time we stamped it.

cached_round_trips is a pure cache: the hourly tick refills it, and a cold cache
simply sends the next search to the provider. Price history lives in
price_observations and is untouched. So the correct repair is to throw it away
and let it rebuild under the new rule.

Revision ID: 20260831_0021
Revises: 20260830_0020
Create Date: 2026-08-31
"""
from alembic import op

revision = "20260831_0021"
down_revision = "20260830_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM cached_round_trips")


def downgrade() -> None:
    # Nothing to restore: this deleted cache entries, and the previous contents
    # were wrong by construction. The cache refills itself either way.
    pass
