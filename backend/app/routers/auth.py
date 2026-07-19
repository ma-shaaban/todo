"""Email/password auth with server-side cookie sessions.

Designed so Google OAuth can slot in later: users.provider + nullable
password_hash already support it (see docs/google-signin-setup.md)."""

import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response

from app import models, security
from app.db import utcnow
from app.deps import CurrentUser, DbSession
from app.schemas import LoginIn, ProfilePatch, SignupIn, user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD = 8
_MAX_NAME = 80


def _create_session(db, user: models.User, request: Request) -> str:
    token = security.new_session_token()
    db.add(
        models.UserSession(
            user_id=user.id,
            token_hash=security.hash_token(token),
            expires_at=utcnow() + timedelta(days=security.SESSION_DAYS),
            user_agent=request.headers.get("user-agent", "")[:400],
        )
    )
    return token


def _validate_display_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Please enter a name")
    if len(name) > _MAX_NAME:
        raise HTTPException(status_code=400, detail=f"Name must be at most {_MAX_NAME} characters")
    return name


@router.post("/signup", status_code=201)
def signup(body: SignupIn, request: Request, response: Response, db: DbSession):
    email = body.email.strip().lower()
    if len(email) > 254 or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(body.password) < _MIN_PASSWORD:
        raise HTTPException(
            status_code=400, detail=f"Password must be at least {_MIN_PASSWORD} characters"
        )
    display_name = _validate_display_name(body.display_name)
    if db.query(models.User).filter(models.User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = models.User(
        email=email,
        password_hash=security.hash_password(body.password),
        display_name=display_name,
    )
    db.add(user)
    db.flush()
    token = _create_session(db, user, request)
    security.set_session_cookie(response, request, token)
    return user_out(user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DbSession):
    email = body.email.strip().lower()
    ip = security.client_ip(request)
    if not security.check_login_rate(email, ip):
        raise HTTPException(
            status_code=429, detail="Too many attempts — try again in a few minutes"
        )
    user = db.query(models.User).filter(models.User.email == email).one_or_none()
    ok = (
        user is not None
        and user.password_hash is not None
        and security.verify_password(user.password_hash, body.password)
    )
    if not ok:
        security.record_login_failure(email, ip)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = _create_session(db, user, request)
    security.set_session_cookie(response, request, token)
    return user_out(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: DbSession):
    token = request.cookies.get(security.SESSION_COOKIE)
    if token:
        db.query(models.UserSession).filter(
            models.UserSession.token_hash == security.hash_token(token)
        ).delete()
    security.clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: CurrentUser):
    return user_out(user)


@router.patch("/me")
def update_me(body: ProfilePatch, user: CurrentUser, db: DbSession):
    if body.display_name is not None:
        user.display_name = _validate_display_name(body.display_name)
    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except Exception:
            raise HTTPException(status_code=400, detail="Unknown timezone")
        user.timezone = body.timezone
    db.add(user)
    return user_out(user)
