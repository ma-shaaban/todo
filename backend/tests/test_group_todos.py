"""Group todos (completion_mode='each'): per-person checks, roll-up,
reminder targeting, membership churn."""

from datetime import datetime, timedelta, timezone

from tests.test_spaces import create_space, invite_code, make_user
from tests.test_todos import add_todo, in_hours, iso

UTC = timezone.utc


def make_pair(client, make_client):
    """Ana (owner) + Bob sharing a space. Returns (space, ana, bob, bob_c)."""
    ana = make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")
    return space, ana, bob, bob_c


def add_group_todo(c, space_id, assignee_ids, title="Pray Fajr", **fields):
    return add_todo(
        c, space_id, title=title, completion_mode="each", assignee_ids=assignee_ids, **fields
    )


def row_for(todo, user_id):
    return next(a for a in todo["assignees"] if a["id"] == user_id)


def test_group_todo_lifecycle(client, make_client):
    space, ana, bob, bob_c = make_pair(client, make_client)
    todo = add_group_todo(client, space["id"], [ana["id"], bob["id"]])
    assert todo["completion_mode"] == "each"
    assert len(todo["assignees"]) == 2
    assert todo["assignee"] is None

    # Ana checks her box: todo stays open, her row is stamped.
    res = client.post(f"/api/todos/{todo['id']}/complete").json()
    assert res["completed"]["completed_at"] is None
    assert row_for(res["completed"], ana["id"])["completed_at"] is not None
    assert row_for(res["completed"], bob["id"])["completed_at"] is None
    assert res["next"] is None

    # Still in the open list for the space.
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    assert [t["id"] for t in items] == [todo["id"]]

    # Bob checks his: the todo completes.
    res = bob_c.post(f"/api/todos/{todo['id']}/complete").json()
    assert res["completed"]["completed_at"] is not None
    assert res["completed"]["completed_by"] == bob["id"]
    assert client.get(f"/api/spaces/{space['id']}/todos").json()["items"] == []
    done = client.get(f"/api/spaces/{space['id']}/todos?status=done").json()["items"]
    assert [t["id"] for t in done] == [todo["id"]]

    # Activity recorded both individual checks and the completion.
    types = [e["type"] for e in client.get(f"/api/spaces/{space['id']}/activity").json()["items"]]
    assert types.count("todo_checked") == 2
    assert types.count("todo_completed") == 1


def test_double_tap_is_idempotent(client, make_client):
    space, ana, bob, _ = make_pair(client, make_client)
    todo = add_group_todo(client, space["id"], [ana["id"], bob["id"]])
    client.post(f"/api/todos/{todo['id']}/complete")
    res = client.post(f"/api/todos/{todo['id']}/complete").json()
    # Second tap claims nothing new and must not complete the parent.
    assert res["completed"]["completed_at"] is None
    types = [e["type"] for e in client.get(f"/api/spaces/{space['id']}/activity").json()["items"]]
    assert types.count("todo_checked") == 1


def test_only_assignees_can_check(client, make_client):
    space, ana, bob, bob_c = make_pair(client, make_client)
    todo = add_group_todo(client, space["id"], [ana["id"]])
    # Bob is a member but not an assignee.
    assert bob_c.post(f"/api/todos/{todo['id']}/complete").status_code == 400
    assert bob_c.post(f"/api/todos/{todo['id']}/reopen").status_code == 400


def test_uncheck_and_reopen_completed(client, make_client):
    space, ana, bob, bob_c = make_pair(client, make_client)
    todo = add_group_todo(client, space["id"], [ana["id"], bob["id"]])
    client.post(f"/api/todos/{todo['id']}/complete")

    # Ana unchecks while still open: row cleared, todo unchanged.
    updated = client.post(f"/api/todos/{todo['id']}/reopen").json()
    assert updated["completed_at"] is None
    assert row_for(updated, ana["id"])["completed_at"] is None

    # Complete fully, then Bob unchecks: the parent reopens, Ana's row stays.
    client.post(f"/api/todos/{todo['id']}/complete")
    bob_c.post(f"/api/todos/{todo['id']}/complete")
    reopened = bob_c.post(f"/api/todos/{todo['id']}/reopen").json()
    assert reopened["completed_at"] is None
    assert row_for(reopened, ana["id"])["completed_at"] is not None
    assert row_for(reopened, bob["id"])["completed_at"] is None


def test_validation(client, make_client):
    space, ana, bob, _ = make_pair(client, make_client)
    r = client.post(
        f"/api/spaces/{space['id']}/todos",
        json={"title": "x", "completion_mode": "each"},
    )
    assert r.status_code == 400
    stranger_c = make_client()
    stranger = make_user(stranger_c, "eve@example.com")
    r = client.post(
        f"/api/spaces/{space['id']}/todos",
        json={"title": "x", "completion_mode": "each", "assignee_ids": [stranger["id"]]},
    )
    assert r.status_code == 400
    r = client.post(
        f"/api/spaces/{space['id']}/todos",
        json={"title": "x", "completion_mode": "bogus"},
    )
    assert r.status_code == 400


def test_my_todos_shows_only_my_pending_check(client, make_client):
    space, ana, bob, bob_c = make_pair(client, make_client)
    todo = add_group_todo(client, space["id"], [ana["id"], bob["id"]])
    assert [t["id"] for t in client.get("/api/me/todos").json()["items"]] == [todo["id"]]
    assert [t["id"] for t in bob_c.get("/api/me/todos").json()["items"]] == [todo["id"]]
    # Ana checks hers → drops off HER list, stays on Bob's.
    client.post(f"/api/todos/{todo['id']}/complete")
    assert client.get("/api/me/todos").json()["items"] == []
    assert [t["id"] for t in bob_c.get("/api/me/todos").json()["items"]] == [todo["id"]]


def test_member_removal_rolls_up(client, make_client):
    space, ana, bob, _ = make_pair(client, make_client)
    todo = add_group_todo(client, space["id"], [ana["id"], bob["id"]])
    # Ana checked; Bob never did and gets kicked → todo rolls up complete.
    client.post(f"/api/todos/{todo['id']}/complete")
    r = client.delete(f"/api/spaces/{space['id']}/members/{bob['id']}")
    assert r.status_code == 200
    done = client.get(f"/api/spaces/{space['id']}/todos?status=done").json()["items"]
    assert [t["id"] for t in done] == [todo["id"]]
    # Bob's unchecked row is gone; Ana's check survives as history.
    assert [a["id"] for a in done[0]["assignees"]] == [ana["id"]]


def test_recurrence_spawns_fresh_rows(client, make_client):
    space, ana, bob, bob_c = make_pair(client, make_client)
    todo = add_group_todo(
        client, space["id"], [ana["id"], bob["id"]],
        due_at=iso(in_hours(1)), recurrence="daily",
    )
    client.post(f"/api/todos/{todo['id']}/complete")
    res = bob_c.post(f"/api/todos/{todo['id']}/complete").json()
    nxt = res["next"]
    assert nxt is not None
    assert nxt["completion_mode"] == "each"
    assert {a["id"] for a in nxt["assignees"]} == {ana["id"], bob["id"]}
    assert all(a["completed_at"] is None for a in nxt["assignees"])


def test_reminder_targets_only_unchecked(client, make_client):
    import sqlalchemy as sa

    from app.services.scheduler import tick_once
    from tests.conftest import test_engine

    space, ana, bob, bob_c = make_pair(client, make_client)
    due = datetime.now(UTC) + timedelta(hours=2)
    todo = add_group_todo(
        client, space["id"], [ana["id"], bob["id"]],
        due_at=iso(due), reminders=[iso(due - timedelta(hours=1))],
    )
    # Ana checks hers, then the reminder comes due → only Bob is nagged.
    client.post(f"/api/todos/{todo['id']}/complete")
    with test_engine().begin() as conn:
        conn.execute(sa.text("UPDATE reminders SET remind_at = now() - interval '1 minute'"))
    assert tick_once() == 1
    ana_notes = [
        n for n in client.get("/api/notifications").json()["items"] if n["type"] == "reminder"
    ]
    bob_notes = [
        n for n in bob_c.get("/api/notifications").json()["items"] if n["type"] == "reminder"
    ]
    assert ana_notes == []
    assert len(bob_notes) == 1
