"""Password hashing, session tokens, login rate limiting, cookie helpers."""

import hashlib
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Request, Response

SESSION_COOKIE = "session"
SESSION_DAYS = 30

_hasher = PasswordHasher()  # argon2id defaults


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Login rate limiting ───────────────────────────────────────────────────
# In-memory sliding window; fine at the deployment's single replica.
_WINDOW_SECONDS = 15 * 60
_MAX_FAILURES = 10
_failures: dict[str, deque] = defaultdict(deque)


def _rate_key(email: str, ip: str) -> str:
    return f"{email.strip().lower()}|{ip}"


def check_login_rate(email: str, ip: str) -> bool:
    """True when another attempt is allowed."""
    q = _failures[_rate_key(email, ip)]
    now = time.monotonic()
    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()
    return len(q) < _MAX_FAILURES


def record_login_failure(email: str, ip: str) -> None:
    _failures[_rate_key(email, ip)].append(time.monotonic())


def reset_rate_limit() -> None:
    _failures.clear()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Session cookie ────────────────────────────────────────────────────────


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    # Behind the platform gateway requests carry x-forwarded-proto=https;
    # plain-http local dev must not set Secure or the browser drops the cookie.
    secure = request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
