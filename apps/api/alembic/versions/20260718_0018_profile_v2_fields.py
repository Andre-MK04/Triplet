"""travel profile v2 fields (base location, smarter budget, tri-state comfort)

Revision ID: 20260718_0018
Revises: 20260718_0017
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "20260718_0018"
down_revision = "20260718_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_travel_profiles", sa.Column("base_location_id", sa.Integer(), nullable=True))
    op.add_column("user_travel_profiles", sa.Column("base_latitude", sa.Float(), nullable=True))
    op.add_column("user_travel_profiles", sa.Column("base_longitude", sa.Float(), nullable=True))
    op.add_column("user_travel_profiles", sa.Column("max_airport_distance_km", sa.Integer(), nullable=True))
    op.add_column(
        "user_travel_profiles",
        sa.Column("recommended_origin_airports", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "user_travel_profiles",
        sa.Column("deal_sensitivity", sa.String(length=20), nullable=False, server_default="balanced"),
    )
    op.add_column("user_travel_profiles", sa.Column("absolute_max_budget", sa.Float(), nullable=True))
    op.add_column(
        "user_travel_profiles",
        sa.Column("alert_trigger_mode", sa.String(length=20), nullable=False, server_default="any"),
    )
    op.add_column(
        "user_travel_profiles",
        sa.Column("comfort_rule_modes", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("user_travel_profiles", sa.Column("theme_preference", sa.String(length=10), nullable=True))
    op.add_column("user_travel_profiles", sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in [
        "onboarding_completed_at", "theme_preference", "comfort_rule_modes", "alert_trigger_mode",
        "absolute_max_budget", "deal_sensitivity", "recommended_origin_airports",
        "max_airport_distance_km", "base_longitude", "base_latitude", "base_location_id",
    ]:
        op.drop_column("user_travel_profiles", col)
