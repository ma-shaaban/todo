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


def test_same_origin_post_allowed(client):
    r = signup(client, headers={"origin": "http://testserver"})
    assert r.status_code == 201
