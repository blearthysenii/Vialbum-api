"""Add private-by-default journey visibility and discovery index.

Revision ID: a61f8c2d904e
Revises: f3a91c7e2d40
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a61f8c2d904e"
down_revision: str | None = "f3a91c7e2d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "journeys", sa.Column("visibility", sa.String(7), nullable=False, server_default="private")
    )
    op.create_check_constraint(
        "ck_journeys_visibility", "journeys", "visibility IN ('private', 'public')"
    )
    op.create_index("ix_journeys_discover", "journeys", ["visibility", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_journeys_discover", table_name="journeys")
    op.drop_constraint("ck_journeys_visibility", "journeys", type_="check")
    op.drop_column("journeys", "visibility")
