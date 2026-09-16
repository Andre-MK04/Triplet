"""Opt-in devices and bounded push delivery outbox."""
from alembic import op
import sqlalchemy as sa

revision = "20260916_0033"
down_revision = "20260916_0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("push_devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", "topic", "environment", name="uq_push_device_token"))
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])
    op.create_table("push_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("push_devices.id"), nullable=False),
        sa.Column("saved_search_id", sa.String(36), sa.ForeignKey("saved_searches.id"), nullable=False),
        sa.Column("alert_run_id", sa.String(36), sa.ForeignKey("alert_runs.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("device_id", "alert_run_id", name="uq_push_delivery_run_device"))
    for column in ["device_id", "saved_search_id", "alert_run_id", "next_attempt_at"]:
        op.create_index("ix_push_deliveries_" + column, "push_deliveries", [column])


def downgrade():
    op.drop_table("push_deliveries")
    op.drop_table("push_devices")
