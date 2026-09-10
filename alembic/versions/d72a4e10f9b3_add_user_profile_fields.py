"""add user profile fields

Revision ID: d72a4e10f9b3
Revises: c84f2d91a6e7
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d72a4e10f9b3"
down_revision: str | None = "c84f2d91a6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("location", sa.String(length=100), nullable=True))
    op.add_column(
        "users", sa.Column("profile_photo_storage_key", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "profile_photo_storage_key")
    op.drop_column("users", "location")
    op.drop_column("users", "bio")
