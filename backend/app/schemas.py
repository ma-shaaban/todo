"""Pydantic request/response bodies. Validation that produces friendly
400s (rather than pydantic 422s) lives in the routers."""

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


def user_out(user) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone,
        "provider": user.provider,
    }
