"""user trial fields

Revision ID: 20260718_0016
Revises: 20260709_0015
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "20260718_0016"
down_revision = "20260709_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("trial_started_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("trial_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "trial_used")
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "trial_started_at")
