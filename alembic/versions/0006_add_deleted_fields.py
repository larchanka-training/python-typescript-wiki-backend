"""add deleted_at and delete_scheduled_at to spaces (if missing)

Revision ID: 0006_add_deleted_fields
Revises: 0005_create_spaces
Create Date: 2026-02-16 12:00:00.000000

"""

from alembic import op

revision = "0006_add_deleted_fields"
down_revision = "0005_create_spaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns only if they don't already exist (safe for existing DBs)
    op.execute(
        """
        ALTER TABLE spaces
        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE spaces
        ADD COLUMN IF NOT EXISTS delete_scheduled_at TIMESTAMP WITH TIME ZONE NULL;
        """
    )


def downgrade() -> None:
    # Remove the columns if present
    op.execute("ALTER TABLE spaces DROP COLUMN IF EXISTS delete_scheduled_at;")
    op.execute("ALTER TABLE spaces DROP COLUMN IF EXISTS deleted_at;")
