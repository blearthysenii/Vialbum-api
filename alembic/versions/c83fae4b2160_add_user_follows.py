"""Add user follow relationships."""

import sqlalchemy as sa

from alembic import op

revision = "c83fae4b2160"
down_revision = "b72e9d3a105f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_follows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "follower_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "following_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("follower_id", "following_id", name="uq_user_follows_pair"),
        sa.CheckConstraint("follower_id != following_id", name="ck_user_follows_not_self"),
    )
    op.create_index(
        "ix_user_follows_follower_page", "user_follows", ["follower_id", "created_at", "id"]
    )
    op.create_index(
        "ix_user_follows_following_page", "user_follows", ["following_id", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_table("user_follows")
