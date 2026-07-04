"""price observations and flight affiliate url

Revision ID: 20260704_0008
Revises: 20260702_0007
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260704_0008"
down_revision = "20260702_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("flights", sa.Column("affiliate_url", sa.String(length=1000), nullable=True))
    op.create_table(
        "price_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("origin_code", sa.String(length=8), nullable=False),
        sa.Column("destination_code", sa.String(length=8), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("observed_price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("observed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default="indicative"),
        sa.Column("link_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("raw_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_price_observations_provider", "price_observations", ["provider"])
    op.create_index("ix_price_observations_origin_code", "price_observations", ["origin_code"])
    op.create_index("ix_price_observations_destination_code", "price_observations", ["destination_code"])
    op.create_index("ix_price_observations_departure_date", "price_observations", ["departure_date"])
    op.create_index("ix_price_observations_observed_at", "price_observations", ["observed_at"])
    op.create_index("ix_price_observations_raw_hash", "price_observations", ["raw_hash"])
    op.create_index(
        "ix_price_observations_route",
        "price_observations",
        ["origin_code", "destination_code", "departure_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_observations_route", table_name="price_observations")
    op.drop_index("ix_price_observations_raw_hash", table_name="price_observations")
    op.drop_index("ix_price_observations_observed_at", table_name="price_observations")
    op.drop_index("ix_price_observations_departure_date", table_name="price_observations")
    op.drop_index("ix_price_observations_destination_code", table_name="price_observations")
    op.drop_index("ix_price_observations_origin_code", table_name="price_observations")
    op.drop_index("ix_price_observations_provider", table_name="price_observations")
    op.drop_table("price_observations")
    op.drop_column("flights", "affiliate_url")
