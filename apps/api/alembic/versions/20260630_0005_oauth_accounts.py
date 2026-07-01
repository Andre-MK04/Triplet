"""oauth accounts

Revision ID: 20260630_0005
Revises: 20260630_0004
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260630_0005"
down_revision = "20260630_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_oauth_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_user_oauth_provider_subject"),
    )
    op.create_index(op.f("ix_user_oauth_accounts_provider"), "user_oauth_accounts", ["provider"], unique=False)
    op.create_index(
        op.f("ix_user_oauth_accounts_provider_user_id"),
        "user_oauth_accounts",
        ["provider_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_user_oauth_accounts_user_id"), "user_oauth_accounts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_oauth_accounts_user_id"), table_name="user_oauth_accounts")
    op.drop_index(op.f("ix_user_oauth_accounts_provider_user_id"), table_name="user_oauth_accounts")
    op.drop_index(op.f("ix_user_oauth_accounts_provider"), table_name="user_oauth_accounts")
    op.drop_table("user_oauth_accounts")
