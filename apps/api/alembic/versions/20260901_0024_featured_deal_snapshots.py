"""Cache the homepage deal board instead of searching per visitor.

The landing page ran a full /trips/search on every page view — a real provider
search, with real cost, repeated for every visitor including crawlers. This
table holds a board computed once per scheduled run and served to everyone.

Revision ID: 20260901_0024
Revises: 20260901_0023
"""

from alembic import op
import sqlalchemy as sa

revision = "20260901_0024"
down_revision = "20260901_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "featured_deal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("trips", sa.JSON(), nullable=False),
        sa.Column("origin_airports", sa.JSON(), nullable=False),
        sa.Column("trip_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Reads are always "the newest snapshot", and cleanup deletes the oldest.
    op.create_index(
        "ix_featured_deal_snapshots_generated_at",
        "featured_deal_snapshots",
        ["generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_featured_deal_snapshots_generated_at", table_name="featured_deal_snapshots")
    op.drop_table("featured_deal_snapshots")
