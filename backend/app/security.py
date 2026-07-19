"""Password hashing, session tokens, login rate limiting, cookie helpers."""

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Request, Response

SESSION_COOKIE = "session"
SESSION_DAYS = 30

# OWASP-recommended argon2id profile (19 MiB, t=2, p=1) instead of the
# library default's 64 MiB per hash: the container runs with a small memory
# limit, and two concurrent signups at 64 MiB each OOM-killed the pod (seen
# live on staging). The semaphore bounds worst-case concurrent hashing
# memory regardless of threadpool width; params ride inside each stored
# hash, so existing hashes keep verifying.
_hasher = PasswordHasher(memory_cost=19_456, time_cost=2, parallelism=1)
_hash_slots = threading.Semaphore(4)


def hash_password(password: str) -> str:
    with _hash_slots:
        return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        with _hash_slots:
            return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Login rate limiting ───────────────────────────────────────────────────
# In-memory sliding windows; fine at the deployment's single replica.
# Two buckets: per email+ip (tight) and per email alone (looser backstop so
# rotating source addresses can't grant unlimited guesses on one account).
_WINDOW_SECONDS = 15 * 60
_MAX_FAILURES = 10
_MAX_EMAIL_FAILURES = 30
_MAX_TRACKED_KEYS = 50_000  # hard memory bound; clearing resets limits, logged
_failures: dict[str, deque] = defaultdict(deque)


def _prune(key: str) -> int:
    """Drop expired timestamps; evict empty keys. Returns remaining count."""
    q = _failures.get(key)
    if q is None:
        return 0
    now = time.monotonic()
    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()
    if not q:
        del _failures[key]
        return 0
    return len(q)


def check_login_rate(email: str, ip: str) -> bool:
    """True when another attempt is allowed."""
    email = email.strip().lower()
    return (
        _prune(f"{email}|{ip}") < _MAX_FAILURES
        and _prune(f"{email}|*") < _MAX_EMAIL_FAILURES
    )


def record_login_failure(email: str, ip: str) -> None:
    if len(_failures) > _MAX_TRACKED_KEYS:
        _failures.clear()
    email = email.strip().lower()
    now = time.monotonic()
    _failures[f"{email}|{ip}"].append(now)
    _failures[f"{email}|*"].append(now)


def reset_rate_limit() -> None:
    _failures.clear()


def client_ip(request: Request) -> str:
    # Rightmost X-Forwarded-For entry: the one the platform gateway (Envoy)
    # itself appended. The leftmost entries are client-supplied and spoofable —
    # trusting them would let an attacker rotate fake IPs past the limiter.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
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
