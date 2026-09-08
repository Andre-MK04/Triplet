"""Track provider delivery events and pseudonymous suppression records.

Revision ID: 20260908_0028
Revises: 20260902_0027
"""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0028"
down_revision = "20260902_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alert_deliveries", sa.Column("provider_message_id", sa.String(length=140), nullable=True))
    op.create_index("ix_alert_deliveries_provider_message_id", "alert_deliveries", ["provider_message_id"])
    op.create_table(
        "email_events",
        sa.Column("svix_id", sa.String(length=140), primary_key=True),
        sa.Column("provider_message_id", sa.String(length=140), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("recipient_hash", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_events_provider_message_id", "email_events", ["provider_message_id"])
    op.create_index("ix_email_events_event_type", "email_events", ["event_type"])
    op.create_index("ix_email_events_recipient_hash", "email_events", ["recipient_hash"])
    op.create_table(
        "email_suppressions",
        sa.Column("recipient_hash", sa.String(length=64), primary_key=True),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("source_event_id", sa.String(length=140), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_suppressions")
    op.drop_index("ix_email_events_recipient_hash", table_name="email_events")
    op.drop_index("ix_email_events_event_type", table_name="email_events")
    op.drop_index("ix_email_events_provider_message_id", table_name="email_events")
    op.drop_table("email_events")
    op.drop_index("ix_alert_deliveries_provider_message_id", table_name="alert_deliveries")
    op.drop_column("alert_deliveries", "provider_message_id")
