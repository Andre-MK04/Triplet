"""cached round trips (deals cache)

Revision ID: 20260708_0014
Revises: 20260708_0013
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260708_0014"
down_revision = "20260708_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cached_round_trips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("origin_code", sa.String(length=8), nullable=False),
        sa.Column("destination_code", sa.String(length=8), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("airline", sa.String(length=120), nullable=True),
        sa.Column("stops", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("booking_url", sa.String(length=1000), nullable=True),
        sa.Column("affiliate_url", sa.String(length=1000), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "origin_code", "destination_code", "departure_date", "return_date",
            name="uq_cached_round_trip_route_dates",
        ),
    )
    op.create_index("ix_cached_round_trips_origin_code", "cached_round_trips", ["origin_code"])
    op.create_index("ix_cached_round_trips_destination_code", "cached_round_trips", ["destination_code"])
    op.create_index("ix_cached_round_trips_observed_at", "cached_round_trips", ["observed_at"])
    # Hot path: fresh deals from a set of origins.
    op.create_index("ix_cached_round_trips_origin_observed", "cached_round_trips", ["origin_code", "observed_at"])


def downgrade() -> None:
    op.drop_index("ix_cached_round_trips_origin_observed", table_name="cached_round_trips")
    op.drop_index("ix_cached_round_trips_observed_at", table_name="cached_round_trips")
    op.drop_index("ix_cached_round_trips_destination_code", table_name="cached_round_trips")
    op.drop_index("ix_cached_round_trips_origin_code", table_name="cached_round_trips")
    op.drop_table("cached_round_trips")
