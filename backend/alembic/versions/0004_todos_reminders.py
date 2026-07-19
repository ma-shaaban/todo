"""todos and reminders tables.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "todos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("space_id", sa.Uuid(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recurrence", sa.Text(), nullable=True),
        sa.Column("recur_anchor_day", sa.SmallInteger(), nullable=True),
        sa.Column("spawned_from", sa.Uuid(), sa.ForeignKey("todos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("position", sa.Double(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_todos_space_id", "todos", ["space_id"])
    op.create_index("ix_todos_assignee_id", "todos", ["assignee_id"])
    op.create_index("ix_todos_space_open", "todos", ["space_id", "completed_at"])

    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("todo_id", sa.Uuid(), sa.ForeignKey("todos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reminders_todo_id", "reminders", ["todo_id"])
    # The poller's claim query scans un-fired reminders by remind_at.
    op.create_index("ix_reminders_due", "reminders", ["remind_at"], postgresql_where=sa.text("fired_at IS NULL"))


def downgrade() -> None:
    op.drop_table("reminders")
    op.drop_table("todos")
