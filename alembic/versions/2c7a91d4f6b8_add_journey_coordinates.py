"""add journey coordinates

Revision ID: 2c7a91d4f6b8
Revises: ef4a9f3c1d20
Create Date: 2026-08-31 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2c7a91d4f6b8"
down_revision: str | None = "ef4a9f3c1d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("journeys", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("journeys", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.create_check_constraint("ck_journeys_latitude", "journeys", "latitude BETWEEN -90 AND 90")
    op.create_check_constraint(
        "ck_journeys_longitude", "journeys", "longitude BETWEEN -180 AND 180"
    )
    op.create_check_constraint(
        "ck_journeys_coordinate_pair",
        "journeys",
        "(latitude IS NULL) = (longitude IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_journeys_coordinate_pair", "journeys", type_="check")
    op.drop_constraint("ck_journeys_longitude", "journeys", type_="check")
    op.drop_constraint("ck_journeys_latitude", "journeys", type_="check")
    op.drop_column("journeys", "longitude")
    op.drop_column("journeys", "latitude")
