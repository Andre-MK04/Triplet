"""billing subscriptions and usage

Revision ID: 20260701_0006
Revises: 20260630_0005
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260701_0006"
down_revision = "20260630_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("plan", sa.String(length=40), nullable=False, server_default="free"))
    op.add_column("users", sa.Column("subscription_status", sa.String(length=40), nullable=False, server_default="none"))
    op.create_index(op.f("ix_users_stripe_customer_id"), "users", ["stripe_customer_id"], unique=False)

    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=120), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=120), nullable=True),
        sa.Column("plan", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("trial_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("raw_last_event_type", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    op.create_index(op.f("ix_billing_subscriptions_stripe_customer_id"), "billing_subscriptions", ["stripe_customer_id"], unique=False)
    op.create_index(op.f("ix_billing_subscriptions_user_id"), "billing_subscriptions", ["user_id"], unique=False)

    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=140), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("processed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_billing_events_stripe_event_id"), "billing_events", ["stripe_event_id"], unique=True)

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("feature", sa.String(length=80), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "feature", "period_start", "period_end", name="uq_usage_user_feature_period"),
    )
    op.create_index(op.f("ix_usage_counters_feature"), "usage_counters", ["feature"], unique=False)
    op.create_index(op.f("ix_usage_counters_user_id"), "usage_counters", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_counters_user_id"), table_name="usage_counters")
    op.drop_index(op.f("ix_usage_counters_feature"), table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index(op.f("ix_billing_events_stripe_event_id"), table_name="billing_events")
    op.drop_table("billing_events")
    op.drop_index(op.f("ix_billing_subscriptions_user_id"), table_name="billing_subscriptions")
    op.drop_index(op.f("ix_billing_subscriptions_stripe_customer_id"), table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")
    op.drop_index(op.f("ix_users_stripe_customer_id"), table_name="users")
    op.drop_column("users", "subscription_status")
    op.drop_column("users", "plan")
    op.drop_column("users", "stripe_customer_id")
