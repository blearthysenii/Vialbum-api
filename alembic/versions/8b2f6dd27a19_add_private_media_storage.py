"""add private media storage metadata and journey covers

Revision ID: 8b2f6dd27a19
Revises: 46dfb59771fc
Create Date: 2026-08-29 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8b2f6dd27a19"
down_revision: str | None = "46dfb59771fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("media", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("media", sa.Column("mime_type", sa.String(length=100), nullable=True))
    op.add_column("media", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("media", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("media", sa.Column("height", sa.Integer(), nullable=True))
    op.add_column("media", sa.Column("thumbnail_storage_key", sa.Text(), nullable=True))

    op.execute("UPDATE media SET storage_key = url WHERE storage_key IS NULL")
    op.execute("UPDATE media SET mime_type = 'application/octet-stream' WHERE mime_type IS NULL")
    op.execute("UPDATE media SET file_size = 0 WHERE file_size IS NULL")
    op.alter_column("media", "storage_key", nullable=False)
    op.alter_column("media", "mime_type", nullable=False)
    op.alter_column("media", "file_size", nullable=False)
    op.create_unique_constraint("uq_media_storage_key", "media", ["storage_key"])
    op.drop_column("media", "thumbnail_url")
    op.drop_column("media", "url")

    op.add_column("journeys", sa.Column("cover_media_id", sa.Uuid(), nullable=True))
    op.create_index("ix_journeys_cover_media_id", "journeys", ["cover_media_id"], unique=False)
    op.create_foreign_key(
        "fk_journeys_cover_media_id_media",
        "journeys",
        "media",
        ["cover_media_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("journeys", "cover_media_url")


def downgrade() -> None:
    op.add_column("journeys", sa.Column("cover_media_url", sa.Text(), nullable=True))
    op.drop_constraint("fk_journeys_cover_media_id_media", "journeys", type_="foreignkey")
    op.drop_index("ix_journeys_cover_media_id", table_name="journeys")
    op.drop_column("journeys", "cover_media_id")

    op.add_column("media", sa.Column("url", sa.Text(), nullable=True))
    op.add_column("media", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    op.execute("UPDATE media SET url = storage_key WHERE url IS NULL")
    op.alter_column("media", "url", nullable=False)
    op.drop_constraint("uq_media_storage_key", "media", type_="unique")
    op.drop_column("media", "thumbnail_storage_key")
    op.drop_column("media", "height")
    op.drop_column("media", "width")
    op.drop_column("media", "file_size")
    op.drop_column("media", "mime_type")
    op.drop_column("media", "original_filename")
    op.drop_column("media", "storage_key")
