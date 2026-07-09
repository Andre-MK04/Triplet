"""trip suggestion itinerary cache

Revision ID: 20260709_0015
Revises: 20260708_0014
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = "20260709_0015"
down_revision = "20260708_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trip_suggestions", sa.Column("itinerary", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("trip_suggestions", "itinerary")
