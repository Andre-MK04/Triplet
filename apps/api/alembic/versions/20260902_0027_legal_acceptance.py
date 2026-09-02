"""Record legal acceptance, and clear raw IPs from session rows.

Nullable on purpose. Accounts created before this migration genuinely did not
record an acceptance, and back-filling one would be inventing evidence — a NULL
says "not recorded", which is the truth.

Revision ID: 20260902_0027
Revises: 20260901_0026
"""

import sqlalchemy as sa
from alembic import op

revision = "20260902_0027"
down_revision = "20260901_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("terms_version", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("privacy_version", sa.String(length=32), nullable=True))

    # refresh_token_sessions.ip_address held the caller's real address. Nothing
    # ever read it — it is not displayed, exported or acted on — so it was
    # personal data retained for no purpose, and it contradicted the privacy
    # policy's claim that Triplet keeps a hash rather than a raw IP. New rows
    # are hashed at write time; the existing values are cleared rather than
    # rewritten, because a hash computed now would only preserve the same
    # linkage the column should not have had.
    op.execute("UPDATE refresh_token_sessions SET ip_address = NULL")


def downgrade() -> None:
    # The cleared addresses are gone for good; a downgrade restores the columns,
    # not the data, and that is the correct outcome.
    op.drop_column("users", "privacy_version")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
