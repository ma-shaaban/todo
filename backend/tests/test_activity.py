from tests.test_spaces import create_space, invite_code, make_user
from tests.test_todos import add_todo


def events(client, space_id, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/api/spaces/{space_id}/activity" + (f"?{q}" if q else ""))
    assert r.status_code == 200
    return r.json()["items"]


def test_activity_records_todo_lifecycle(client):
    make_user(client, "ana@example.com", name="Ana")
    space = create_space(client)
    todo = add_todo(client, space["id"], title="Buy milk")
    client.post(f"/api/todos/{todo['id']}/complete")
    client.post(f"/api/todos/{todo['id']}/reopen")
    client.delete(f"/api/todos/{todo['id']}")

    types = [e["type"] for e in events(client, space["id"])]
    # Newest first.
    assert types == ["todo_deleted", "todo_reopened", "todo_completed", "todo_created"]
    deleted = events(client, space["id"])[0]
    assert deleted["actor"]["display_name"] == "Ana"
    assert deleted["data"]["title"] == "Buy milk"


def test_activity_records_membership_and_rename(client, make_client):
    make_user(client, "ana@example.com", name="Ana")
    space = create_space(client, "Family")
    code = invite_code(client, space["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com", name="Bob")
    bob_c.post(f"/api/invites/{code}/accept")
    client.patch(f"/api/spaces/{space['id']}", json={"name": "Casa"})
    bob_c.delete(f"/api/spaces/{space['id']}/members/{bob['id']}")  # leave

    types = [e["type"] for e in events(client, space["id"])]
    assert types == ["member_left", "space_renamed", "member_joined"]


def test_assignment_recorded_with_names(client, make_client):
    make_user(client, "ana@example.com", name="Ana")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com", name="Bob")
    bob_c.post(f"/api/invites/{code}/accept")
    add_todo(client, space["id"], title="Dishes", assignee_id=bob["id"])

    items = events(client, space["id"])
    assigned = [e for e in items if e["type"] == "todo_assigned"]
    assert len(assigned) == 1
    assert assigned[0]["data"]["assignee_name"] == "Bob"


def test_activity_requires_membership(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    stranger = make_client()
    make_user(stranger, "eve@example.com")
    assert stranger.get(f"/api/spaces/{space['id']}/activity").status_code == 404


def test_activity_pagination(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    for i in range(5):
        add_todo(client, space["id"], title=f"t{i}")
    first = events(client, space["id"], limit=2)
    assert len(first) == 2
    older = events(client, space["id"], limit=50, before=first[-1]["created_at"])
    assert len(older) == 3
    assert first[-1]["created_at"] > older[0]["created_at"]