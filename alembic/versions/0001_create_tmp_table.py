from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_create_tmp_table"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tmp",
        sa.Column("id", sa.Integer(), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("tmp")

