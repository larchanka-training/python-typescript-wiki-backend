"""fix articles schema: FK on-delete, nullable owner, new columns

Revision ID: 0008_fix_articles_schema
Revises: 0007_create_articles
Create Date: 2026-03-01 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "0008_fix_articles_schema"
down_revision = "0007_create_articles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── articles table ──────────────────────────────────────────────

    # 1. Rename author_id → owner_id and make nullable
    op.alter_column("articles", "author_id", new_column_name="owner_id", nullable=True)

    # 2. Drop old FK constraints (no explicit name → use convention)
    op.drop_constraint("articles_author_id_fkey", "articles", type_="foreignkey")
    op.drop_constraint("articles_space_id_fkey", "articles", type_="foreignkey")

    # 3. Drop old indexes for author_id
    op.drop_index("ix_articles_author_id", table_name="articles")

    # 4. Re-create FK with ON DELETE
    op.create_foreign_key(
        "articles_owner_id_fkey", "articles", "users",
        ["owner_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "articles_space_id_fkey", "articles", "spaces",
        ["space_id"], ["id"], ondelete="CASCADE",
    )

    # 5. Re-create index for owner_id
    op.create_index("ix_articles_owner_id", "articles", ["owner_id"])

    # 6. Add new columns to articles
    op.add_column("articles", sa.Column("parent_id", sa.UUID(), nullable=True))
    op.add_column("articles", sa.Column("position", sa.Integer(), server_default="0", nullable=False))
    op.add_column("articles", sa.Column("version_id", sa.UUID(), nullable=True))

    # FK: parent_id → articles.id (self-referencing, CASCADE)
    op.create_foreign_key(
        "articles_parent_id_fkey", "articles", "articles",
        ["parent_id"], ["id"], ondelete="SET NULL",
    )

    # ── article_versions table ──────────────────────────────────────

    # 1. Make author_id nullable
    op.alter_column("article_versions", "author_id", nullable=True)

    # 2. Drop old FK constraints
    op.drop_constraint("article_versions_article_id_fkey", "article_versions", type_="foreignkey")
    op.drop_constraint("article_versions_author_id_fkey", "article_versions", type_="foreignkey")

    # 3. Re-create FK with ON DELETE
    op.create_foreign_key(
        "article_versions_article_id_fkey", "article_versions", "articles",
        ["article_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "article_versions_author_id_fkey", "article_versions", "users",
        ["author_id"], ["id"], ondelete="SET NULL",
    )

    # 4. Add new columns
    op.add_column(
        "article_versions",
        sa.Column("show_toc", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "article_versions",
        sa.Column("content_format", sa.String(32), server_default="markdown", nullable=False),
    )
    op.add_column(
        "article_versions",
        sa.Column("change_summary", sa.String(500), nullable=True),
    )

    # FK: articles.version_id → article_versions.id (after versions table is updated)
    op.create_foreign_key(
        "articles_version_id_fkey", "articles", "article_versions",
        ["version_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    # ── Undo article_versions changes ──
    op.drop_constraint("articles_version_id_fkey", "articles", type_="foreignkey")

    op.drop_column("article_versions", "change_summary")
    op.drop_column("article_versions", "content_format")
    op.drop_column("article_versions", "show_toc")

    op.drop_constraint("article_versions_author_id_fkey", "article_versions", type_="foreignkey")
    op.drop_constraint("article_versions_article_id_fkey", "article_versions", type_="foreignkey")

    op.create_foreign_key(
        "article_versions_author_id_fkey", "article_versions", "users",
        ["author_id"], ["id"],
    )
    op.create_foreign_key(
        "article_versions_article_id_fkey", "article_versions", "articles",
        ["article_id"], ["id"],
    )

    op.alter_column("article_versions", "author_id", nullable=False)

    # ── Undo articles changes ──
    op.drop_constraint("articles_parent_id_fkey", "articles", type_="foreignkey")
    op.drop_column("articles", "version_id")
    op.drop_column("articles", "position")
    op.drop_column("articles", "parent_id")

    op.drop_index("ix_articles_owner_id", table_name="articles")
    op.drop_constraint("articles_owner_id_fkey", "articles", type_="foreignkey")
    op.drop_constraint("articles_space_id_fkey", "articles", type_="foreignkey")

    op.create_foreign_key(
        "articles_space_id_fkey", "articles", "spaces",
        ["space_id"], ["id"],
    )
    op.create_foreign_key(
        "articles_author_id_fkey", "articles", "users",
        ["owner_id"], ["id"],
    )
    op.create_index("ix_articles_author_id", "articles", ["owner_id"])

    op.alter_column("articles", "owner_id", new_column_name="author_id", nullable=False)
