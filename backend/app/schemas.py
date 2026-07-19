"""Pydantic request/response bodies. Validation that produces friendly
400s (rather than pydantic 422s) lives in the routers."""

from datetime import datetime

from pydantic import BaseModel


class SignupIn(BaseModel):
    email: str
    password: str
    display_name: str


class LoginIn(BaseModel):
    email: str
    password: str


class ProfilePatch(BaseModel):
    display_name: str | None = None
    timezone: str | None = None


class SpaceIn(BaseModel):
    name: str


class TodoCreate(BaseModel):
    title: str
    notes: str = ""
    due_at: datetime | None = None
    priority: int = 0
    assignee_id: str | None = None
    # completion_mode 'each': every user in assignee_ids checks off their
    # own completion; the todo completes when the last one does.
    completion_mode: str = "any"
    assignee_ids: list[str] | None = None
    recurrence: str | None = None
    position: float = 0.0
    reminders: list[datetime] = []


class TodoPatch(BaseModel):
    """PATCH semantics: an omitted field is untouched; an explicit null
    clears it (distinguished via model_fields_set)."""

    title: str | None = None
    notes: str | None = None
    due_at: datetime | None = None
    priority: int | None = None
    assignee_id: str | None = None
    recurrence: str | None = None
    position: float | None = None
    reminders: list[datetime] | None = None


def user_out(user) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone,
        "provider": user.provider,
    }
