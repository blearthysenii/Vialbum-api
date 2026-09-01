"""add normalized places

Revision ID: 91c3d81a7e42
Revises: 2c7a91d4f6b8
Create Date: 2026-09-01 13:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "91c3d81a7e42"
down_revision: str | None = "2c7a91d4f6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "places",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_place_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("locality", sa.String(length=160), nullable=True),
        sa.Column("region", sa.String(length=160), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_places_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_places_longitude"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_place_id", name="uq_places_provider_identity"),
    )
    op.add_column("journeys", sa.Column("place_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_journeys_place_id"), "journeys", ["place_id"], unique=False)
    op.create_foreign_key(
        "fk_journeys_place_id_places",
        "journeys",
        "places",
        ["place_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_journeys_place_id_places", "journeys", type_="foreignkey")
    op.drop_index(op.f("ix_journeys_place_id"), table_name="journeys")
    op.drop_column("journeys", "place_id")
    op.drop_table("places")
