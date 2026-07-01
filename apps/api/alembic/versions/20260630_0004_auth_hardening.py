"""auth hardening

Revision ID: 20260630_0004
Revises: 20260630_0003
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260630_0004"
down_revision = "20260630_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET password_hash = 'disabled' WHERE password_hash IS NULL")
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=300),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=300),
        nullable=True,
    )
