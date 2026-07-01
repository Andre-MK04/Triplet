"""initial schema

Revision ID: 20260629_0001
Revises:
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260629_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "airport_areas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_airport_areas_slug"), "airport_areas", ["slug"], unique=True)

    op.create_table(
        "airports",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("area_id", sa.Integer(), nullable=True),
        sa.Column("is_user_origin_candidate", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["airport_areas.id"]),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "flights",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("origin_code", sa.String(length=8), nullable=False),
        sa.Column("destination_code", sa.String(length=8), nullable=False),
        sa.Column("departure_datetime", sa.DateTime(), nullable=False),
        sa.Column("arrival_datetime", sa.DateTime(), nullable=False),
        sa.Column("airline", sa.String(length=120), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("booking_url", sa.String(length=500), nullable=True),
        sa.Column("baggage_included", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("observed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["destination_code"], ["airports.code"]),
        sa.ForeignKeyConstraint(["origin_code"], ["airports.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flights_destination_code"), "flights", ["destination_code"], unique=False)
    op.create_index(op.f("ix_flights_origin_code"), "flights", ["origin_code"], unique=False)

    op.create_table(
        "ground_transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_airport_code", sa.String(length=8), nullable=False),
        sa.Column("to_airport_code", sa.String(length=8), nullable=False),
        sa.Column("from_city", sa.String(length=120), nullable=False),
        sa.Column("to_city", sa.String(length=120), nullable=False),
        sa.Column("duration_hours", sa.Float(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["from_airport_code"], ["airports.code"]),
        sa.ForeignKeyConstraint(["to_airport_code"], ["airports.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_airport_code", "to_airport_code", name="uq_transfer_airports"),
    )
    op.create_index(op.f("ix_ground_transfers_from_airport_code"), "ground_transfers", ["from_airport_code"], unique=False)
    op.create_index(op.f("ix_ground_transfers_to_airport_code"), "ground_transfers", ["to_airport_code"], unique=False)

    op.create_table(
        "search_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("origin_airports", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("min_trip_length_days", sa.Integer(), nullable=False),
        sa.Column("max_trip_length_days", sa.Integer(), nullable=False),
        sa.Column("max_budget", sa.Float(), nullable=False),
        sa.Column("max_ground_transfer_hours", sa.Float(), nullable=False),
        sa.Column("trip_style", sa.String(length=40), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("search_logs")
    op.drop_index(op.f("ix_ground_transfers_to_airport_code"), table_name="ground_transfers")
    op.drop_index(op.f("ix_ground_transfers_from_airport_code"), table_name="ground_transfers")
    op.drop_table("ground_transfers")
    op.drop_index(op.f("ix_flights_origin_code"), table_name="flights")
    op.drop_index(op.f("ix_flights_destination_code"), table_name="flights")
    op.drop_table("flights")
    op.drop_table("airports")
    op.drop_index(op.f("ix_airport_areas_slug"), table_name="airport_areas")
    op.drop_table("airport_areas")
