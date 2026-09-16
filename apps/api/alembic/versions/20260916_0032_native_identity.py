"""Native Apple nonce challenges and encrypted provider revocation tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20260916_0032"
down_revision = "20260916_0031"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("native_auth_challenges", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("nonce_hash", sa.String(64), nullable=False),
                    sa.Column("expires_at", sa.DateTime(), nullable=False),
                    sa.Column("consumed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_native_auth_challenges_expires_at", "native_auth_challenges", ["expires_at"])
    op.add_column("user_oauth_accounts", sa.Column("encrypted_refresh_token", sa.Text(), nullable=True))
    op.add_column("user_oauth_accounts", sa.Column("native_client_id", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("user_oauth_accounts", "native_client_id")
    op.drop_column("user_oauth_accounts", "encrypted_refresh_token")
    op.drop_table("native_auth_challenges")
