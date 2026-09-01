"""Anonymous watches must prove they own the email before they can send to it.

A watch created anonymously names an address nobody has demonstrated control
of, and it went active immediately — so anyone could point Triplet's fare
emails at an arbitrary inbox. These columns carry the double opt-in.

Existing rows are backfilled as verified: they predate the check, deactivating
them would silently break watches people rely on, and they were created under
the old contract. New anonymous watches start unverified.

Revision ID: 20260901_0023
Revises: 20260831_0022
"""

from alembic import op
import sqlalchemy as sa

revision = "20260901_0023"
down_revision = "20260831_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("saved_searches", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.add_column("saved_searches", sa.Column("verification_token_hash", sa.String(length=128), nullable=True))
    op.add_column("saved_searches", sa.Column("verification_sent_at", sa.DateTime(), nullable=True))
    op.add_column("saved_searches", sa.Column("verification_expires_at", sa.DateTime(), nullable=True))

    # Grandfather existing watches rather than silently muting them.
    op.execute("UPDATE saved_searches SET email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP)")

    # Verification lookup is by token hash alone, and stale-unverified cleanup
    # scans by verification_expires_at.
    op.create_index(
        "ix_saved_searches_verification_token_hash",
        "saved_searches",
        ["verification_token_hash"],
    )
    op.create_index(
        "ix_saved_searches_verification_expires_at",
        "saved_searches",
        ["verification_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_saved_searches_verification_expires_at", table_name="saved_searches")
    op.drop_index("ix_saved_searches_verification_token_hash", table_name="saved_searches")
    op.drop_column("saved_searches", "verification_expires_at")
    op.drop_column("saved_searches", "verification_sent_at")
    op.drop_column("saved_searches", "verification_token_hash")
    op.drop_column("saved_searches", "email_verified_at")
