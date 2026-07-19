"""Shared FastAPI dependencies (current user, db session)."""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as OrmSession

from app import models, security
from app.db import get_db, utcnow

# scope="function": the session teardown (commit) runs before the response is
# sent, so commit failures become error responses, never phantom successes.
DbSession = Annotated[OrmSession, Depends(get_db, scope="function")]


def get_current_user(request: Request, response: Response, db: DbSession) -> models.User:
    token = request.cookies.get(security.SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess = (
        db.query(models.UserSession)
        .filter(models.UserSession.token_hash == security.hash_token(token))
        .one_or_none()
    )
    now = utcnow()
    if sess is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if sess.expires_at <= now:
        # Opportunistic cleanup; committed here because the 401 below makes
        # the request-level teardown roll back.
        db.delete(sess)
        db.commit()
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Rolling expiry: extend the DB row AND re-issue the cookie (a cookie's
    # Max-Age is fixed at set time — without re-setting it the browser would
    # still drop the session 30 days after login, however active the user).
    if sess.expires_at - now < timedelta(days=15):
        sess.expires_at = now + timedelta(days=security.SESSION_DAYS)
        security.set_session_cookie(response, request, token)
    user = db.get(models.User, sess.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]
