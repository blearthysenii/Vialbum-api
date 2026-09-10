"""add case-insensitive unique usernames

Revision ID: c84f2d91a6e7
Revises: b52e8049c3a1
Create Date: 2026-09-09
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c84f2d91a6e7"
down_revision: str | None = "b52e8049c3a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _username_base(email: str) -> str:
    local_part = email.split("@", 1)[0].casefold()
    base = re.sub(r"[^a-z0-9_]", "_", local_part).strip("_")
    if len(base) < 3:
        base = f"user_{base}" if base else "user"
    return base[:30]


def upgrade() -> None:
    connection = op.get_bind()
    duplicate_emails = connection.execute(
        sa.text(
            "SELECT lower(email) AS normalized_email, count(*) AS total "
            "FROM users GROUP BY lower(email) HAVING count(*) > 1"
        )
    ).fetchall()
    if duplicate_emails:
        duplicates = ", ".join(str(row.normalized_email) for row in duplicate_emails)
        raise RuntimeError(
            "Case-insensitive duplicate user emails must be resolved before migration: "
            f"{duplicates}"
        )

    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    users = connection.execute(
        sa.text("SELECT id, email FROM users ORDER BY created_at, id")
    ).fetchall()
    used: set[str] = set()
    for user in users:
        base = _username_base(user.email)
        candidate = base
        suffix = 2
        while candidate.casefold() in used:
            suffix_text = f"_{suffix}"
            candidate = f"{base[: 30 - len(suffix_text)]}{suffix_text}"
            suffix += 1
        used.add(candidate.casefold())
        connection.execute(
            sa.text("UPDATE users SET username = :username WHERE id = :user_id"),
            {"username": candidate, "user_id": user.id},
        )

    op.alter_column("users", "username", existing_type=sa.String(length=30), nullable=False)
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.drop_column("users", "username")
