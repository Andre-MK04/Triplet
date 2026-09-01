"""Let each watch decide what is worth an email.

The trigger lived on the user's travel profile, so it applied to every watch an
account had: you could not follow one route for any fare at all and another only
for an unusually cheap one. Anonymous watches could not choose at all and always
got "any".

The column is nullable and left NULL for existing rows. NULL means "use the
account's preference, or 'any'" — exactly what every watch did before — so
nothing changes for anyone until they choose. Backfilling a concrete value would
record a decision no traveller actually made.

Revision ID: 20260901_0026
Revises: 20260901_0025
"""

from alembic import op
import sqlalchemy as sa

revision = "20260901_0026"
down_revision = "20260901_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("saved_searches", sa.Column("trigger_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("saved_searches", "trigger_mode")
