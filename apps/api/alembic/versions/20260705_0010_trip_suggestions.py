"""trip suggestions

Revision ID: 20260705_0010
Revises: 20260704_0009
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "20260705_0010"
down_revision = "20260704_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_suggestions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("saved_search_id", sa.String(length=36), sa.ForeignKey("saved_searches.id"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("trip_type", sa.String(length=20), nullable=False),
        sa.Column("origin_airport", sa.String(length=8), nullable=False),
        sa.Column("outbound_destination", sa.String(length=8), nullable=False),
        sa.Column("return_origin", sa.String(length=8), nullable=True),
        sa.Column("final_arrival_airport", sa.String(length=8), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("deal_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_trip_suggestions_user_id", "trip_suggestions", ["user_id"])
    op.create_index("ix_trip_suggestions_saved_search_id", "trip_suggestions", ["saved_search_id"])
    op.create_index("ix_trip_suggestions_origin_airport", "trip_suggestions", ["origin_airport"])
    op.create_index("ix_trip_suggestions_outbound_destination", "trip_suggestions", ["outbound_destination"])
    op.create_index("ix_trip_suggestions_created_at", "trip_suggestions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_trip_suggestions_created_at", table_name="trip_suggestions")
    op.drop_index("ix_trip_suggestions_outbound_destination", table_name="trip_suggestions")
    op.drop_index("ix_trip_suggestions_origin_airport", table_name="trip_suggestions")
    op.drop_index("ix_trip_suggestions_saved_search_id", table_name="trip_suggestions")
    op.drop_index("ix_trip_suggestions_user_id", table_name="trip_suggestions")
    op.drop_table("trip_suggestions")
