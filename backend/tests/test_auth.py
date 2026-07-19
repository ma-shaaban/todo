import pytest

from app import security


@pytest.fixture(autouse=True)
def reset_rate_limit():
    security.reset_rate_limit()
    yield
    security.reset_rate_limit()


def signup(client, email="ana@example.com", password="sup3rsecret", name="Ana", **kw):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "display_name": name},
        **kw,
    )


def test_signup_sets_cookie_and_me_works(client):
    r = signup(client)
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "ana@example.com"
    assert data["display_name"] == "Ana"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"
    assert me.json()["provider"] == "local"


def test_signup_cookie_flags(client):
    r = signup(client)
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_me_unauthenticated(client):
    assert client.get("/api/auth/me").status_code == 401


def test_duplicate_email_case_insensitive(client):
    signup(client)
    r = signup(client, email="ANA@Example.com")
    assert r.status_code == 409


def test_weak_password(client):
    assert signup(client, password="short").status_code == 400


def test_invalid_email(client):
    assert signup(client, email="not-an-email").status_code == 400


def test_empty_display_name(client):
    assert signup(client, name="   ").status_code == 400


def test_login_wrong_password_and_unknown_email_same_answer(client):
    signup(client)
    r1 = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrongwrong"})
    r2 = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"})
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_logout_kills_session_and_login_normalizes_email(client):
    signup(client)
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    # Login with different case + stray whitespace still works.
    r = client.post("/api/auth/login", json={"email": " Ana@Example.com ", "password": "sup3rsecret"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_login_rate_limited_after_repeated_failures(client):
    signup(client)
    for _ in range(10):
        r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "badbadbad"})
        assert r.status_code == 401
    # Even the correct password is refused once the window is exhausted.
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "sup3rsecret"})
    assert r.status_code == 429


def test_patch_me(client):
    signup(client)
    r = client.patch("/api/auth/me", json={"display_name": "Ana Banana", "timezone": "Africa/Cairo"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Ana Banana"
    assert client.get("/api/auth/me").json()["timezone"] == "Africa/Cairo"


def test_patch_me_rejects_bad_timezone(client):
    signup(client)
    assert client.patch("/api/auth/me", json={"timezone": "Mars/Olympus"}).status_code == 400


def test_cross_origin_post_rejected(client):
    r = signup(client, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_null_origin_post_rejected(client):
    # "Origin: null" (sandboxed iframes, file://) is definitively cross-origin.
    r = signup(client, headers={"origin": "null"})
    assert r.status_code == 403


def test_same_origin_post_allowed(client):
    r = signup(client, headers={"origin": "http://testserver"})
    assert r.status_code == 201


def test_rate_limit_ignores_spoofed_left_xff_entries(client):
    # The leftmost X-Forwarded-For entries are client-supplied; only the
    # rightmost (gateway-appended) one counts. Rotating fakes must not
    # grant fresh rate-limit buckets.
    signup(client)
    for i in range(10):
        r = client.post(
            "/api/auth/login",
            json={"email": "ana@example.com", "password": "badbadbad"},
            headers={"x-forwarded-for": f"{i}.{i}.{i}.{i}, 10.0.0.99"},
        )
        assert r.status_code == 401
    r = client.post(
        "/api/auth/login",
        json={"email": "ana@example.com", "password": "sup3rsecret"},
        headers={"x-forwarded-for": "99.99.99.99, 10.0.0.99"},
    )
    assert r.status_code == 429


def test_per_email_backstop_limits_rotating_ips(client):
    # Even with fully distinct source IPs, one email can't take unlimited
    # guesses: the per-email backstop trips at 30 failures.
    signup(client)
    for i in range(30):
        r = client.post(
            "/api/auth/login",
            json={"email": "ana@example.com", "password": "badbadbad"},
            headers={"x-forwarded-for": f"1.2.{i // 250}.{i % 250}"},
        )
        assert r.status_code == 401
    r = client.post(
        "/api/auth/login",
        json={"email": "ana@example.com", "password": "sup3rsecret"},
        headers={"x-forwarded-for": "8.8.8.8"},
    )
    assert r.status_code == 429


def test_login_with_oauth_style_account_is_401_not_500(client, migrated_db):
    # A user without a password (future Google sign-in) must get the same
    # 401 as a wrong password — not a server error.
    from app import models
    from app.db import get_engine
    from sqlalchemy.orm import Session as OrmSession

    with OrmSession(get_engine()) as s:
        s.add(models.User(email="oauth@example.com", password_hash=None, display_name="O"))
        s.commit()
    r = client.post("/api/auth/login", json={"email": "oauth@example.com", "password": "whatever1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


def test_huge_password_rejected(client):
    assert signup(client, password="x" * 2000).status_code == 400


def test_commit_failure_is_503_not_phantom_success(client, monkeypatch):
    # The session commits BEFORE the response is sent (function-scoped
    # dependency); a commit-time DB failure must surface as the JSON 503,
    # never a 201 whose rows silently vanished.
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session as OrmSession

    def boom(self):
        raise OperationalError("commit", None, Exception("connection lost"))

    monkeypatch.setattr(OrmSession, "commit", boom)
    r = signup(client, email="doomed@example.com")
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()


def test_expired_session_row_deleted_when_presented(client, migrated_db):
    import sqlalchemy as sa

    from tests.conftest import test_engine

    signup(client)
    with test_engine().begin() as conn:
        n = conn.execute(sa.text("UPDATE sessions SET expires_at = now() - interval '1 day'")).rowcount
        assert n == 1
    assert client.get("/api/auth/me").status_code == 401
    with test_engine().begin() as conn:
        left = conn.execute(sa.text("SELECT count(*) FROM sessions")).scalar()
    assert left == 0


def test_rolling_expiry_reissues_cookie(client, migrated_db):
    import sqlalchemy as sa

    from tests.conftest import test_engine

    signup(client)
    # Backdate the session into the final 15-day window.
    with test_engine().begin() as conn:
        conn.execute(sa.text("UPDATE sessions SET expires_at = now() + interval '5 days'"))
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert "session=" in r.headers.get("set-cookie", "")
    with test_engine().begin() as conn:
        days = conn.execute(
            sa.text("SELECT extract(epoch FROM (expires_at - now())) / 86400 FROM sessions")
        ).scalar()
    assert days > 29
