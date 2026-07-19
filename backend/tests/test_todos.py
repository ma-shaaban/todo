from datetime import datetime, timedelta, timezone

from tests.test_spaces import create_space, invite_code, make_user

UTC = timezone.utc


def iso(dt):
    return dt.astimezone(UTC).isoformat()


def in_hours(h):
    return datetime.now(UTC) + timedelta(hours=h)


def add_todo(c, space_id, title="Buy milk", **fields):
    r = c.post(f"/api/spaces/{space_id}/todos", json={"title": title, **fields})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list_todo(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    todo = add_todo(client, space["id"], notes="2 liters", priority=2, due_at=iso(in_hours(3)))
    assert todo["title"] == "Buy milk"
    assert todo["notes"] == "2 liters"
    assert todo["priority"] == 2
    assert todo["assignee"] is None
    assert todo["completed_at"] is None
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    assert [t["id"] for t in items] == [todo["id"]]
    # Space list now counts it.
    assert client.get("/api/spaces").json()["items"][0]["todo_count"] == 1


def test_title_required_and_priority_bounds(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    assert client.post(f"/api/spaces/{space['id']}/todos", json={"title": "  "}).status_code == 400
    assert client.post(
        f"/api/spaces/{space['id']}/todos", json={"title": "x", "priority": 9}
    ).status_code == 400
    assert client.post(
        f"/api/spaces/{space['id']}/todos", json={"title": "x", "recurrence": "hourly"}
    ).status_code == 400


def test_non_member_cannot_see_or_touch(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    todo = add_todo(client, space["id"])
    stranger = make_client()
    make_user(stranger, "eve@example.com")
    assert stranger.get(f"/api/spaces/{space['id']}/todos").status_code == 404
    assert stranger.post(f"/api/spaces/{space['id']}/todos", json={"title": "x"}).status_code == 404
    assert stranger.patch(f"/api/todos/{todo['id']}", json={"title": "hacked"}).status_code == 404
    assert stranger.delete(f"/api/todos/{todo['id']}").status_code == 404
    assert stranger.post(f"/api/todos/{todo['id']}/complete").status_code == 404


def test_assignee_must_be_member(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")
    outsider_c = make_client()
    outsider = make_user(outsider_c, "eve@example.com")

    todo = add_todo(client, space["id"], assignee_id=bob["id"])
    assert todo["assignee"]["display_name"] == "bob"
    r = client.post(
        f"/api/spaces/{space['id']}/todos", json={"title": "x", "assignee_id": outsider["id"]}
    )
    assert r.status_code == 400


def test_patch_updates_and_reminder_replacement(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    due = in_hours(24)
    todo = add_todo(
        client, space["id"], due_at=iso(due), reminders=[iso(due - timedelta(hours=1))]
    )
    assert len(todo["reminders"]) == 1
    # Patch with a new reminder list replaces the un-fired one.
    r = client.patch(
        f"/api/todos/{todo['id']}",
        json={"reminders": [iso(due - timedelta(hours=2)), iso(due - timedelta(minutes=30))]},
    )
    assert r.status_code == 200
    assert len(r.json()["reminders"]) == 2
    # Patch without 'reminders' leaves them alone.
    r = client.patch(f"/api/todos/{todo['id']}", json={"title": "Renamed"})
    assert len(r.json()["reminders"]) == 2
    # Clearing works.
    r = client.patch(f"/api/todos/{todo['id']}", json={"reminders": []})
    assert r.json()["reminders"] == []


def test_complete_and_reopen(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    todo = add_todo(client, space["id"])
    r = client.post(f"/api/todos/{todo['id']}/complete")
    assert r.status_code == 200
    body = r.json()
    assert body["completed"]["completed_at"] is not None
    assert body["next"] is None
    # Completing again is a no-op, not a second spawn.
    again = client.post(f"/api/todos/{todo['id']}/complete").json()
    assert again["next"] is None
    # Done list shows it; open list doesn't.
    assert client.get(f"/api/spaces/{space['id']}/todos").json()["items"] == []
    done = client.get(f"/api/spaces/{space['id']}/todos?status=done").json()["items"]
    assert [t["id"] for t in done] == [todo["id"]]
    # Reopen.
    assert client.post(f"/api/todos/{todo['id']}/reopen").status_code == 200
    assert len(client.get(f"/api/spaces/{space['id']}/todos").json()["items"]) == 1


def test_completing_recurring_spawns_next_with_shifted_reminders(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    due = in_hours(5)
    todo = add_todo(
        client,
        space["id"],
        title="Water plants",
        due_at=iso(due),
        recurrence="daily",
        priority=1,
        reminders=[iso(due - timedelta(hours=1))],
    )
    body = client.post(f"/api/todos/{todo['id']}/complete").json()
    nxt = body["next"]
    assert nxt is not None
    assert nxt["title"] == "Water plants"
    assert nxt["recurrence"] == "daily"
    assert nxt["priority"] == 1
    # Next due exactly one day later; reminder keeps its 1h offset.
    next_due = datetime.fromisoformat(nxt["due_at"])
    assert abs((next_due - due) - timedelta(days=1)) < timedelta(seconds=2)
    assert len(nxt["reminders"]) == 1
    next_reminder = datetime.fromisoformat(nxt["reminders"][0]["remind_at"])
    assert abs((next_due - next_reminder) - timedelta(hours=1)) < timedelta(seconds=2)
    # The open list contains only the spawned occurrence.
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    assert [t["id"] for t in items] == [nxt["id"]]


def test_recurrence_requires_due_date(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    r = client.post(
        f"/api/spaces/{space['id']}/todos", json={"title": "x", "recurrence": "daily"}
    )
    assert r.status_code == 400


def test_ordering(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    no_due = add_todo(client, space["id"], title="someday")
    later = add_todo(client, space["id"], title="later", due_at=iso(in_hours(48)))
    soon_high = add_todo(client, space["id"], title="soon-high", due_at=iso(in_hours(2)), priority=3)
    soon_low = add_todo(client, space["id"], title="soon-low", due_at=iso(in_hours(2)), priority=1)
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    assert [t["title"] for t in items] == ["soon-high", "soon-low", "later", "someday"]


def test_my_tasks_across_spaces(client, make_client):
    ana = make_user(client, "ana@example.com")
    home = create_space(client, "Home")
    work = create_space(client, "Work")
    code = invite_code(client, home["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")

    mine_unassigned = add_todo(client, home["id"], title="mine-unassigned")
    add_todo(client, work["id"], title="work-thing", assignee_id=ana["id"])
    assigned_to_bob = add_todo(client, home["id"], title="for-bob", assignee_id=bob["id"])
    bob_created_unassigned = add_todo(bob_c, home["id"], title="bob-created")

    my = client.get("/api/me/todos").json()["items"]
    titles = {t["title"] for t in my}
    assert titles == {"mine-unassigned", "work-thing"}
    assert all("space" in t and t["space"]["name"] for t in my)

    bobs = bob_c.get("/api/me/todos").json()["items"]
    assert {t["title"] for t in bobs} == {"for-bob", "bob-created"}

    # Completed items drop out of my-tasks.
    client.post(f"/api/todos/{mine_unassigned['id']}/complete")
    my = client.get("/api/me/todos").json()["items"]
    assert {t["title"] for t in my} == {"work-thing"}


def test_reminders_rejected_in_past_or_naive(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    r = client.post(
        f"/api/spaces/{space['id']}/todos",
        json={"title": "x", "reminders": [iso(datetime.now(UTC) - timedelta(hours=2))]},
    )
    assert r.status_code == 400


def test_space_delete_cascades_todos(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    due = in_hours(4)
    add_todo(client, space["id"], due_at=iso(due), reminders=[iso(due - timedelta(hours=1))])
    assert client.delete(f"/api/spaces/{space['id']}").status_code == 200
    import sqlalchemy as sa

    from tests.conftest import test_engine

    with test_engine().begin() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM todos")).scalar() == 0
        assert conn.execute(sa.text("SELECT count(*) FROM reminders")).scalar() == 0
