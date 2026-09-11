"""add profile cover photo

Revision ID: f3a91c7e2d40
Revises: d72a4e10f9b3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a91c7e2d40"
down_revision: str | None = "d72a4e10f9b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("profile_cover_storage_key", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "profile_cover_storage_key")
