"""saved search alerts

Revision ID: 20260630_0002
Revises: 20260629_0001
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260630_0002"
down_revision = "20260629_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("origin_airports", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("min_trip_length_days", sa.Integer(), nullable=False),
        sa.Column("max_trip_length_days", sa.Integer(), nullable=False),
        sa.Column("max_budget", sa.Float(), nullable=False),
        sa.Column("max_ground_transfer_hours", sa.Float(), nullable=False),
        sa.Column("trip_style", sa.String(length=40), nullable=False),
        sa.Column("direct_only", sa.Boolean(), nullable=True),
        sa.Column("include_baggage", sa.Boolean(), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_notified_at", sa.DateTime(), nullable=True),
        sa.Column("last_best_price", sa.Float(), nullable=True),
        sa.Column("last_best_trip_id", sa.String(length=120), nullable=True),
        sa.Column("manage_token_hash", sa.String(length=128), nullable=False),
        sa.Column("unsubscribe_token_hash", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_saved_searches_email"), "saved_searches", ["email"], unique=False)

    op.create_table(
        "alert_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("saved_search_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("provider_used", sa.String(length=80), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("best_price", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["saved_search_id"], ["saved_searches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_runs_saved_search_id"), "alert_runs", ["saved_search_id"], unique=False)

    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("saved_search_id", sa.String(length=36), nullable=False),
        sa.Column("alert_run_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["alert_run_id"], ["alert_runs.id"]),
        sa.ForeignKeyConstraint(["saved_search_id"], ["saved_searches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_deliveries_alert_run_id"), "alert_deliveries", ["alert_run_id"], unique=False)
    op.create_index(op.f("ix_alert_deliveries_saved_search_id"), "alert_deliveries", ["saved_search_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_alert_deliveries_saved_search_id"), table_name="alert_deliveries")
    op.drop_index(op.f("ix_alert_deliveries_alert_run_id"), table_name="alert_deliveries")
    op.drop_table("alert_deliveries")
    op.drop_index(op.f("ix_alert_runs_saved_search_id"), table_name="alert_runs")
    op.drop_table("alert_runs")
    op.drop_index(op.f("ix_saved_searches_email"), table_name="saved_searches")
    op.drop_table("saved_searches")
