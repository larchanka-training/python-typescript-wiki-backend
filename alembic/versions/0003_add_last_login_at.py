"""Добавляет last_login_at и делает username nullable.

last_login_at нужен для фиксации последнего успешного входа.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_add_last_login_at"
down_revision = "0002_create_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_login_at column and allow username to be nullable."""
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.alter_column("users", "username", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    """Revert last_login_at and username nullability changes."""
    op.alter_column("users", "username", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("users", "last_login_at")
