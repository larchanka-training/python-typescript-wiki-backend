"""Add spaces, space members, and superuser flag."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_add_spaces_and_roles"
down_revision = "0004_create_sessions_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add spaces, membership roles, and users.is_superuser."""
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "spaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "space_members",
        sa.Column(
            "space_id",
            sa.Integer(),
            sa.ForeignKey("spaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'editor', 'viewer')",
            name="ck_space_members_role",
        ),
    )
    op.create_index("ix_space_members_user_id", "space_members", ["user_id"])


def downgrade() -> None:
    """Drop spaces, membership roles, and users.is_superuser."""
    op.drop_index("ix_space_members_user_id", table_name="space_members")
    op.drop_table("space_members")
    op.drop_table("spaces")
    op.drop_column("users", "is_superuser")
