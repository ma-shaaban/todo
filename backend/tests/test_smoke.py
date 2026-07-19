def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_hello(client):
    r = client.get("/api/hello")
    assert r.status_code == 200


def test_db_check(client):
    r = client.get("/api/db-check")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


def test_unknown_api_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_version(client):
    r = client.get("/api/version")
    assert r.status_code == 200
    assert "version" in r.json()
