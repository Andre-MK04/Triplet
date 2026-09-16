"""Private observed-fare bookmarks (not active watches).

Revision ID: 20260915_0030
Revises: 20260914_0029
"""

import sqlalchemy as sa
from alembic import op

revision = "20260915_0030"
down_revision = "20260914_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_fares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("suggestion_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("trip_type", sa.String(20), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("fare_status", sa.String(20), nullable=False, server_default="indicative"),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("check_price_url", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "suggestion_id", name="uq_saved_fare_user_suggestion"),
    )
    op.create_index("ix_saved_fares_user_id", "saved_fares", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_fares_user_id", table_name="saved_fares")
    op.drop_table("saved_fares")
