"""personal travel map country relationships and visits

Revision ID: 20260818_0019
Revises: 20260718_0018
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa

revision = "20260818_0019"
down_revision = "20260718_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_countries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("visited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("wishlist", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("relationship_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "country_code", name="uq_user_country"),
    )
    op.create_index("ix_user_countries_user_id", "user_countries", ["user_id"])
    op.create_index("ix_user_countries_country_code", "user_countries", ["country_code"])

    op.create_table(
        "country_visits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("user_country_id", sa.String(length=36), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="visit"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("start_precision", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("end_precision", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("trip_suggestion_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_country_id"], ["user_countries.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_country_visits_user_id", "country_visits", ["user_id"])
    op.create_index("ix_country_visits_user_country_id", "country_visits", ["user_country_id"])
    op.create_index("ix_country_visits_country_code", "country_visits", ["country_code"])
    op.create_index("ix_country_visits_trip_suggestion_id", "country_visits", ["trip_suggestion_id"])


def downgrade() -> None:
    op.drop_table("country_visits")
    op.drop_table("user_countries")
