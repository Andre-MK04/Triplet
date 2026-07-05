"""user travel profiles

Revision ID: 20260704_0009
Revises: 20260704_0008
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260704_0009"
down_revision = "20260704_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_travel_profiles",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("home_location", sa.String(length=160), nullable=True),
        sa.Column("origin_airports", sa.JSON(), nullable=False),
        sa.Column("max_airport_travel_time_minutes", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("preferred_trip_types", sa.JSON(), nullable=False),
        sa.Column("preferred_trip_length_min", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("preferred_trip_length_max", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("budget_comfort_zone", sa.String(length=40), nullable=False, server_default="under_200"),
        sa.Column("spontaneity", sa.String(length=40), nullable=False, server_default="next_month"),
        sa.Column("comfort_rules", sa.JSON(), nullable=False),
        sa.Column("open_jaw_willingness", sa.String(length=40), nullable=False, server_default="simple_returns_only"),
        sa.Column("notification_frequency", sa.String(length=40), nullable=False, server_default="weekly_digest"),
        sa.Column("excluded_airlines", sa.JSON(), nullable=False),
        sa.Column("preferred_months", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_travel_profiles")
