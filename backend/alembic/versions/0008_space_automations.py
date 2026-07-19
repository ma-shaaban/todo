"""Space automations (pluggable providers) + idempotency keys on todos.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("spaces", sa.Column("automation_type", sa.Text(), nullable=True))
    op.add_column("spaces", sa.Column("automation_config", sa.JSON(), nullable=True))
    op.add_column("todos", sa.Column("automation_key", sa.Text(), nullable=True))
    # Providers re-run every tick; this is what makes them idempotent.
    op.create_index(
        "ux_todos_automation_key",
        "todos",
        ["space_id", "automation_key"],
        unique=True,
        postgresql_where=sa.text("automation_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_todos_automation_key")
    op.drop_column("todos", "automation_key")
    op.drop_column("spaces", "automation_config")
    op.drop_column("spaces", "automation_type")
