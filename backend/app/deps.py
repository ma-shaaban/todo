"""Shared FastAPI dependencies (current user, db session)."""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as OrmSession

from app import models
from app.db import get_db, utcnow
from app.security import SESSION_COOKIE, hash_token

DbSession = Annotated[OrmSession, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> models.User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess = (
        db.query(models.UserSession)
        .filter(models.UserSession.token_hash == hash_token(token))
        .one_or_none()
    )
    now = utcnow()
    if sess is None or sess.expires_at <= now:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Rolling expiry: active users stay signed in (PWA-friendly).
    if sess.expires_at - now < timedelta(days=15):
        sess.expires_at = now + timedelta(days=30)
    user = db.get(models.User, sess.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]
