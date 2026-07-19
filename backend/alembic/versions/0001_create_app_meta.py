"""create app_meta table

Example migration — proves the alembic pipeline end to end. Add your own
schema with `alembic revision -m "..."` (new files land next to this one).

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_meta",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("app_meta")
