"""Preserve normalized saved itineraries and semantic watch criteria."""

import sqlalchemy as sa
from alembic import op

revision = "20260916_0031"
down_revision = "20260915_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("saved_fares", sa.Column("itinerary_snapshot", sa.JSON(), nullable=True))
    op.add_column("saved_searches", sa.Column("search_criteria", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("saved_searches", "search_criteria")
    op.drop_column("saved_fares", "itinerary_snapshot")
