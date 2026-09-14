"""Add single-use native email verification codes.

Revision ID: 20260914_0029
Revises: 20260908_0028
"""

import sqlalchemy as sa
from alembic import op

revision = "20260914_0029"
down_revision = "20260908_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "native_email_verification_codes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_native_email_verification_codes_user_id",
        "native_email_verification_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_native_email_verification_codes_code_hash",
        "native_email_verification_codes",
        ["code_hash"],
    )
    op.create_index(
        "ix_native_email_verification_codes_expires_at",
        "native_email_verification_codes",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_email_verification_codes_expires_at",
        table_name="native_email_verification_codes",
    )
    op.drop_index(
        "ix_native_email_verification_codes_code_hash",
        table_name="native_email_verification_codes",
    )
    op.drop_index(
        "ix_native_email_verification_codes_user_id",
        table_name="native_email_verification_codes",
    )
    op.drop_table("native_email_verification_codes")
