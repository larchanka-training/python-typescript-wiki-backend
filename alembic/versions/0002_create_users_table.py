"""Create users table for token verification flow."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_create_users_table"
down_revision = "0001_create_tmp_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the users table with a unique telegram_id."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("photo_url", sa.String(length=1024), nullable=True),
        sa.Column("permission", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )


def downgrade() -> None:
    """Drop the users table."""
    op.drop_table("users")
