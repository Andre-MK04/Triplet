"""skyscanner flight metadata

Revision ID: 20260702_0007
Revises: 20260701_0006
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260702_0007"
down_revision = "20260701_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("flights", sa.Column("provider_offer_id", sa.String(length=160), nullable=True))
    op.add_column("flights", sa.Column("deep_link", sa.String(length=1000), nullable=True))
    op.add_column("flights", sa.Column("agent_name", sa.String(length=160), nullable=True))
    op.add_column("flights", sa.Column("stops", sa.Integer(), nullable=True))
    op.add_column("flights", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.add_column("flights", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("flights", sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("flights", sa.Column("raw_provider_hash", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("flights", "raw_provider_hash")
    op.drop_column("flights", "is_live")
    op.drop_column("flights", "expires_at")
    op.drop_column("flights", "duration_minutes")
    op.drop_column("flights", "stops")
    op.drop_column("flights", "agent_name")
    op.drop_column("flights", "deep_link")
    op.drop_column("flights", "provider_offer_id")
