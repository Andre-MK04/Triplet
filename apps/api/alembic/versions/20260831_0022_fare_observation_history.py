"""long-lived fare observation history

price_observations already existed but recorded only one-way candidate flights,
with no trip type, no provider "found at" timestamp, and deduplication that
expired after an hour. Round-trip observations — the fares almost every search
actually displays — were never stored at all.

This widens the table into a durable, provider-agnostic record of price events
and makes deduplication a database guarantee rather than a timed window.

Revision ID: 20260831_0022
Revises: 20260831_0021
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = "20260831_0022"
down_revision = "20260831_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_observations", sa.Column("observation_kind", sa.String(length=32),
                                                  nullable=False, server_default="cached_provider"))
    op.add_column("price_observations", sa.Column("trip_type", sa.String(length=16),
                                                  nullable=False, server_default="one_way"))
    op.add_column("price_observations", sa.Column("nights", sa.Integer(), nullable=True))
    op.add_column("price_observations", sa.Column("found_at", sa.DateTime(), nullable=True))
    op.add_column("price_observations", sa.Column("stops", sa.Integer(), nullable=True))
    op.add_column("price_observations", sa.Column("airline", sa.String(length=120), nullable=True))

    op.create_index("ix_price_observations_observation_kind", "price_observations", ["observation_kind"])
    op.create_index("ix_price_observations_trip_type", "price_observations", ["trip_type"])
    op.create_index("ix_price_observations_found_at", "price_observations", ["found_at"])
    op.create_index("ix_price_observation_route_date", "price_observations",
                    ["origin_code", "destination_code", "departure_date"])
    op.create_index("ix_price_observation_route_trip", "price_observations",
                    ["origin_code", "destination_code", "trip_type"])

    # Deduplication becomes a constraint, so no code path can double-count a
    # price event. Existing rows were deduplicated only within a one-hour
    # window, so collapse any repeats first — they are duplicates by definition.
    op.execute(
        """
        DELETE FROM price_observations
        WHERE id NOT IN (SELECT MIN(id) FROM price_observations GROUP BY raw_hash)
        """
    )
    # A unique INDEX rather than a table constraint: it gives the identical
    # guarantee and, unlike ALTER TABLE ADD CONSTRAINT, is supported on SQLite
    # as well as Postgres, so local and production migrate the same way.
    op.create_index(
        "uq_price_observation_identity", "price_observations", ["raw_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_price_observation_identity", table_name="price_observations")
    op.drop_index("ix_price_observation_route_trip", table_name="price_observations")
    op.drop_index("ix_price_observation_route_date", table_name="price_observations")
    op.drop_index("ix_price_observations_found_at", table_name="price_observations")
    op.drop_index("ix_price_observations_trip_type", table_name="price_observations")
    op.drop_index("ix_price_observations_observation_kind", table_name="price_observations")
    for column in ("airline", "stops", "found_at", "nights", "trip_type", "observation_kind"):
        op.drop_column("price_observations", column)
