"""create tmp table

Revision ID: f3d1b2c4a5e6
Revises: 
Create Date: 2025-12-16

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f3d1b2c4a5e6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tmp",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tmp")

