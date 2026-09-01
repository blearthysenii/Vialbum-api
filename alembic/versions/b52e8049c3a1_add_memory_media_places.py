"""add memory and media places

Revision ID: b52e8049c3a1
Revises: 91c3d81a7e42
Create Date: 2026-09-01 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b52e8049c3a1"
down_revision: str | None = "91c3d81a7e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("place_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_memories_place_id"), "memories", ["place_id"], unique=False)
    op.create_foreign_key(
        "fk_memories_place_id_places",
        "memories",
        "places",
        ["place_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_memories_coordinate_pair",
        "memories",
        "(latitude IS NULL) = (longitude IS NULL)",
    )
    op.add_column("media", sa.Column("place_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_media_place_id"), "media", ["place_id"], unique=False)
    op.create_foreign_key(
        "fk_media_place_id_places",
        "media",
        "places",
        ["place_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_media_coordinate_pair",
        "media",
        "(latitude IS NULL) = (longitude IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_media_coordinate_pair", "media", type_="check")
    op.drop_constraint("fk_media_place_id_places", "media", type_="foreignkey")
    op.drop_index(op.f("ix_media_place_id"), table_name="media")
    op.drop_column("media", "place_id")
    op.drop_constraint("ck_memories_coordinate_pair", "memories", type_="check")
    op.drop_constraint("fk_memories_place_id_places", "memories", type_="foreignkey")
    op.drop_index(op.f("ix_memories_place_id"), table_name="memories")
    op.drop_column("memories", "place_id")
