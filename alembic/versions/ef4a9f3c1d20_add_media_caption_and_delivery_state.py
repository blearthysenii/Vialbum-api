"""add media caption and delivery state

Revision ID: ef4a9f3c1d20
Revises: 8b2f6dd27a19
Create Date: 2026-08-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ef4a9f3c1d20"
down_revision: str | None = "8b2f6dd27a19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="refresh_sessions_token_hash_key"),
    )
    op.create_index(
        "ix_refresh_sessions_expires_at", "refresh_sessions", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_refresh_sessions_token_hash", "refresh_sessions", ["token_hash"], unique=False
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"], unique=False)
    op.add_column("media", sa.Column("display_storage_key", sa.Text(), nullable=True))
    op.add_column(
        "media", sa.Column("deletion_pending_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("media", sa.Column("caption", sa.Text(), nullable=True))
    op.create_index("ix_media_deletion_pending_at", "media", ["deletion_pending_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_token_hash", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_expires_at", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_index("ix_media_deletion_pending_at", table_name="media")
    op.drop_column("media", "caption")
    op.drop_column("media", "deletion_pending_at")
    op.drop_column("media", "display_storage_key")
