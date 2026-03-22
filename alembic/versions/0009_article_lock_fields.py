"""add is_locked column to articles

Revision ID: 0009_article_lock_fields
Revises: 0008_fix_articles_schema
Create Date: 2026-03-22 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "0009_article_lock_fields"
down_revision = "0008_fix_articles_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("is_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("articles", "is_locked")
