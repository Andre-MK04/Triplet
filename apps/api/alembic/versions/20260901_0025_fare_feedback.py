"""Record how observed fares hold up when travellers check them.

Triplet shows observed rather than live prices and has never had data on how far
they drift by the time someone looks. This table collects that, from travellers
who volunteer it after following a live-price link.

Nothing here identifies a person: no user id, no address. check_id is a random
per-click value whose only job is to stop one check being answered twice.

Revision ID: 20260901_0025
Revises: 20260901_0024
"""

from alembic import op
import sqlalchemy as sa

revision = "20260901_0025"
down_revision = "20260901_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fare_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("check_id", sa.String(length=64), nullable=False),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("destination", sa.String(length=8), nullable=False),
        sa.Column("trip_type", sa.String(length=20), nullable=False),
        sa.Column("fare_kind", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("fare_age_bucket", sa.String(length=16), nullable=False),
        sa.Column("shown_price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("response", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    # One answer per check. A unique index rather than a unique constraint so
    # the migration applies on SQLite as well as PostgreSQL.
    op.create_index("ix_fare_feedback_check_id", "fare_feedback", ["check_id"], unique=True)
    # The aggregates group by these, so they are indexed for the reads that exist
    # rather than speculatively.
    op.create_index("ix_fare_feedback_route", "fare_feedback", ["origin", "destination"])
    op.create_index("ix_fare_feedback_age_bucket", "fare_feedback", ["fare_age_bucket"])
    op.create_index("ix_fare_feedback_fare_kind", "fare_feedback", ["fare_kind"])
    op.create_index("ix_fare_feedback_created_at", "fare_feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_fare_feedback_created_at", table_name="fare_feedback")
    op.drop_index("ix_fare_feedback_fare_kind", table_name="fare_feedback")
    op.drop_index("ix_fare_feedback_age_bucket", table_name="fare_feedback")
    op.drop_index("ix_fare_feedback_route", table_name="fare_feedback")
    op.drop_index("ix_fare_feedback_check_id", table_name="fare_feedback")
    op.drop_table("fare_feedback")
