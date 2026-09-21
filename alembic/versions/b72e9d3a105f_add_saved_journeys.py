"""Add saved journey relationships.

Revision ID: b72e9d3a105f
Revises: a61f8c2d904e
"""

import sqlalchemy as sa

from alembic import op

revision = "b72e9d3a105f"
down_revision = "a61f8c2d904e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_journeys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "journey_id",
            sa.Uuid(),
            sa.ForeignKey("journeys.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "journey_id", name="uq_saved_journeys_user_journey"),
    )
    op.create_index("ix_saved_journeys_page", "saved_journeys", ["user_id", "created_at", "id"])
    op.create_index("ix_saved_journeys_journey_id", "saved_journeys", ["journey_id"])


def downgrade() -> None:
    op.drop_table("saved_journeys")
