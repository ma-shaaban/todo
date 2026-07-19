import pytest

from tests.test_spaces import create_space, invite_code, make_user

SUB = {
    "endpoint": "https://push.example.com/sub/abc123",
    "keys": {"p256dh": "BPubKeyFake", "auth": "authFake"},
}


@pytest.fixture(autouse=True)
def captured_pushes(monkeypatch):
    """Capture outgoing web pushes instead of hitting the network."""
    sent = []

    def fake_webpush(subscription_info, data, **kwargs):
        sent.append({"sub": subscription_info, "data": data, "kwargs": kwargs})

    from app.services import notify

    monkeypatch.setattr(notify, "webpush", fake_webpush)
    yield sent


def test_vapid_public_key_is_stable_without_env(client):
    r1 = client.get("/api/push/vapid-public-key")
    assert r1.status_code == 200
    key = r1.json()["key"]
    assert len(key) > 40
    assert client.get("/api/push/vapid-public-key").json()["key"] == key


def test_subscribe_requires_auth(client):
    assert client.post("/api/push/subscriptions", json=SUB).status_code == 401


def test_subscribe_and_unsubscribe(client):
    make_user(client, "ana@example.com")
    assert client.post("/api/push/subscriptions", json=SUB).status_code == 201
    # Idempotent upsert.
    assert client.post("/api/push/subscriptions", json=SUB).status_code == 201
    r = client.request("DELETE", "/api/push/subscriptions", json={"endpoint": SUB["endpoint"]})
    assert r.status_code == 204


def test_subscribe_same_endpoint_reassigns_to_new_user(client, make_client):
    make_user(client, "ana@example.com")
    client.post("/api/push/subscriptions", json=SUB)
    bob = make_client()
    make_user(bob, "bob@example.com")
    assert bob.post("/api/push/subscriptions", json=SUB).status_code == 201
    import sqlalchemy as sa

    from tests.conftest import test_engine

    with test_engine().begin() as conn:
        count = conn.execute(sa.text("SELECT count(*) FROM push_subscriptions")).scalar()
    assert count == 1


def test_assignment_notifies_assignee(client, make_client, captured_pushes):
    make_user(client, "ana@example.com", name="Ana")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com", name="Bob")
    bob_c.post(f"/api/invites/{code}/accept")
    bob_c.post("/api/push/subscriptions", json=SUB)

    client.post(f"/api/spaces/{space['id']}/todos", json={"title": "Dishes", "assignee_id": bob["id"]})

    r = bob_c.get("/api/notifications")
    assert r.status_code == 200
    items = r.json()["items"]
    joined_types = [i["type"] for i in items]
    assert "assigned" in joined_types
    assigned = next(i for i in items if i["type"] == "assigned")
    assert "Ana" in assigned["title"] and "Dishes" in assigned["title"]
    assert r.json()["unread_count"] >= 1
    # Web push went to bob's subscription.
    assert any("Dishes" in p["data"] for p in captured_pushes)


def test_self_assignment_does_not_notify(client, captured_pushes):
    ana = make_user(client, "ana@example.com")
    space = create_space(client)
    client.post(f"/api/spaces/{space['id']}/todos", json={"title": "Solo", "assignee_id": ana["id"]})
    assert client.get("/api/notifications").json()["items"] == []


def test_completion_notifies_creator(client, make_client):
    make_user(client, "ana@example.com", name="Ana")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    make_user(bob_c, "bob@example.com", name="Bob")
    bob_c.post(f"/api/invites/{code}/accept")

    todo = client.post(f"/api/spaces/{space['id']}/todos", json={"title": "Trash"}).json()
    bob_c.post(f"/api/todos/{todo['id']}/complete")

    items = client.get("/api/notifications").json()["items"]
    completed = [i for i in items if i["type"] == "completed"]
    assert len(completed) == 1
    assert "Bob" in completed[0]["title"] and "Trash" in completed[0]["title"]


def test_join_notifies_existing_members(client, make_client):
    make_user(client, "ana@example.com", name="Ana")
    space = create_space(client, "Family")
    code = invite_code(client, space["id"])
    bob_c = make_client()
    make_user(bob_c, "bob@example.com", name="Bob")
    bob_c.post(f"/api/invites/{code}/accept")

    items = client.get("/api/notifications").json()["items"]
    joined = [i for i in items if i["type"] == "joined"]
    assert len(joined) == 1
    assert "Bob" in joined[0]["title"] and "Family" in joined[0]["title"]


def test_read_and_read_all(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client, "Family")
    code = invite_code(client, space["id"])
    for i in range(2):
        c = make_client()
        make_user(c, f"m{i}@example.com", name=f"M{i}")
        c.post(f"/api/invites/{code}/accept")

    r = client.get("/api/notifications")
    assert r.json()["unread_count"] == 2
    first = r.json()["items"][0]
    assert client.post(f"/api/notifications/{first['id']}/read").status_code == 200
    assert client.get("/api/notifications").json()["unread_count"] == 1
    assert client.post("/api/notifications/read-all").status_code == 200
    assert client.get("/api/notifications").json()["unread_count"] == 0


def test_cannot_read_others_notifications(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client, "Family")
    code = invite_code(client, space["id"])
    bob_c = make_client()
    make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")
    note = client.get("/api/notifications").json()["items"][0]
    assert bob_c.post(f"/api/notifications/{note['id']}/read").status_code == 404
