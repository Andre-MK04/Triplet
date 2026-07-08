"""drop flights->airports foreign keys

Flights are dynamic provider data spanning any European airport/metro code
(e.g. STO, PAR, MOW), which need not exist in the curated airports table.
The foreign keys caused cache inserts to fail and broke live search.

Revision ID: 20260708_0013
Revises: 20260707_0012
Create Date: 2026-07-08
"""
from alembic import op

revision = "20260708_0013"
down_revision = "20260707_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (tests) builds schema from models via create_all and never had
        # these named constraints; nothing to drop.
        return
    op.drop_constraint("flights_origin_code_fkey", "flights", type_="foreignkey")
    op.drop_constraint("flights_destination_code_fkey", "flights", type_="foreignkey")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.create_foreign_key("flights_origin_code_fkey", "flights", "airports", ["origin_code"], ["code"])
    op.create_foreign_key("flights_destination_code_fkey", "flights", "airports", ["destination_code"], ["code"])
