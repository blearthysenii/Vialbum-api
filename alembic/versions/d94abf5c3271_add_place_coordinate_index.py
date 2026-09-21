"""Index normalized places for viewport discovery."""

from alembic import op

revision = "d94abf5c3271"
down_revision = "c83fae4b2160"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_places_coordinates", "places", ["latitude", "longitude"])


def downgrade():
    op.drop_index("ix_places_coordinates", table_name="places")
