"""Group todos: per-assignee completion (completion_mode='each').

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "todos",
        sa.Column("completion_mode", sa.Text(), nullable=False, server_default="any"),
    )
    op.create_table(
        "todo_assignees",
        sa.Column(
            "todo_id",
            sa.Uuid(),
            sa.ForeignKey("todos.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # My Tasks queries by user; the PK already covers todo-side lookups.
    op.create_index("ix_todo_assignees_user", "todo_assignees", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_todo_assignees_user")
    op.drop_table("todo_assignees")
    op.drop_column("todos", "completion_mode")
