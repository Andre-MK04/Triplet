"""locations + airport directory tables

Revision ID: 20260718_0017
Revises: 20260718_0016
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "20260718_0017"
down_revision = "20260718_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("ascii_name", sa.String(length=200), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("country_name", sa.String(length=80), nullable=False),
        sa.Column("admin_region", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=60), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="geonames"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_ascii_name", "locations", ["ascii_name"])
    op.create_index("ix_locations_country_code", "locations", ["country_code"])

    op.create_table(
        "airport_directory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iata_code", sa.String(length=3), nullable=False),
        sa.Column("icao_code", sa.String(length=4), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("city", sa.String(length=160), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("country_name", sa.String(length=80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("scheduled_service", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="ourairports"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_airport_directory_iata_code", "airport_directory", ["iata_code"], unique=True)
    op.create_index("ix_airport_directory_name", "airport_directory", ["name"])
    op.create_index("ix_airport_directory_city", "airport_directory", ["city"])
    op.create_index("ix_airport_directory_country_code", "airport_directory", ["country_code"])


def downgrade() -> None:
    op.drop_table("airport_directory")
    op.drop_table("locations")
