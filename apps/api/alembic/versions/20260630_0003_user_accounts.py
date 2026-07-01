"""user accounts

Revision ID: 20260630_0003
Revises: 20260630_0002
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260630_0003"
down_revision = "20260630_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=300), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.add_column("saved_searches", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_saved_searches_user_id"), "saved_searches", ["user_id"], unique=False)
    op.create_foreign_key("fk_saved_searches_user_id_users", "saved_searches", "users", ["user_id"], ["id"])

    op.create_table(
        "refresh_token_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_refresh_token_sessions_token_hash"), "refresh_token_sessions", ["token_hash"], unique=False)
    op.create_index(op.f("ix_refresh_token_sessions_user_id"), "refresh_token_sessions", ["user_id"], unique=False)

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_password_reset_tokens_token_hash"), "password_reset_tokens", ["token_hash"], unique=False)
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False)

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_verification_tokens_token_hash"), "email_verification_tokens", ["token_hash"], unique=False)
    op.create_index(op.f("ix_email_verification_tokens_user_id"), "email_verification_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_token_hash"), table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(op.f("ix_refresh_token_sessions_user_id"), table_name="refresh_token_sessions")
    op.drop_index(op.f("ix_refresh_token_sessions_token_hash"), table_name="refresh_token_sessions")
    op.drop_table("refresh_token_sessions")
    op.drop_constraint("fk_saved_searches_user_id_users", "saved_searches", type_="foreignkey")
    op.drop_index(op.f("ix_saved_searches_user_id"), table_name="saved_searches")
    op.drop_column("saved_searches", "user_id")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
