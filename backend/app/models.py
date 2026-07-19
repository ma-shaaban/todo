"""ORM models. Schema changes always come with an alembic migration —
the models and migrations must stay in sync by hand (no autogenerate wired)."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.Text, unique=True, index=True)  # stored lowercase
    password_hash: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # null for OAuth users
    display_name: Mapped[str] = mapped_column(sa.Text)
    provider: Mapped[str] = mapped_column(sa.Text, default="local", server_default="local")
    timezone: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utcnow, server_default=sa.func.now()
    )


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(sa.Text, unique=True)  # sha256 of the cookie token
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utcnow, server_default=sa.func.now()
    )
    user_agent: Mapped[str] = mapped_column(sa.Text, default="", server_default="")
