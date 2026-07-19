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


def test_static_resolution_and_traversal_guard(tmp_path, monkeypatch):
    """Nested static paths (PWA icons, sw.js) resolve; traversal never does."""
    from pathlib import Path

    from app import main

    static = tmp_path / "static"
    (static / "icons").mkdir(parents=True)
    (static / "index.html").write_text("<html>app</html>")
    (static / "icons" / "icon.png").write_text("png-bytes")
    (tmp_path / "secret.txt").write_text("nope")

    monkeypatch.setattr(main, "_static", Path(static))
    hit = main._resolve_static_file("icons/icon.png")
    assert hit is not None and hit.name == "icon.png"
    assert main._resolve_static_file("index.html") is not None
    assert main._resolve_static_file("../secret.txt") is None  # traversal blocked
    assert main._resolve_static_file("missing.png") is None
    assert main._resolve_static_file("") is None
