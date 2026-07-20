from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from tests.conftest import test_engine
from tests.test_spaces import create_space, invite_code, make_user
from tests.test_todos import add_todo, iso

UTC = timezone.utc


@pytest.fixture(autouse=True)
def captured_pushes(monkeypatch):
    sent = []

    def fake_webpush(subscription_info, data, **kwargs):
        sent.append({"sub": subscription_info, "data": data, "kwargs": kwargs})

    from app.services import notify

    monkeypatch.setattr(notify, "webpush", fake_webpush)
    yield sent


def backdate_reminders():
    with test_engine().begin() as conn:
        conn.execute(sa.text("UPDATE reminders SET remind_at = now() - interval '1 minute'"))


def tick():
    from app.services.scheduler import tick_once

    return tick_once()


def test_due_reminder_fires_exactly_once(client, captured_pushes):
    make_user(client, "ana@example.com")
    space = create_space(client)
    due = datetime.now(UTC) + timedelta(hours=2)
    add_todo(client, space["id"], title="Meds", due_at=iso(due), reminders=[iso(due - timedelta(hours=1))])
    backdate_reminders()

    sub = {"endpoint": "https://push.example.com/ana", "keys": {"p256dh": "k", "auth": "a"}}
    client.post("/api/push/subscriptions", json=sub)

    assert tick() == 1
    assert tick() == 0  # claimed — never double-fires
    items = client.get("/api/notifications").json()["items"]
    reminders = [i for i in items if i["type"] == "reminder"]
    assert len(reminders) == 1
    assert "Meds" in reminders[0]["title"]
    assert any("Meds" in p["data"] for p in captured_pushes)
    # The push payload carries what the service worker needs for the
    # "Mark done" notification action.
    import json as _json

    payload = _json.loads(captured_pushes[0]["data"])
    assert payload["type"] == "reminder"
    assert payload["todo_id"]


def test_assigned_reminder_targets_assignee_only(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")

    due = datetime.now(UTC) + timedelta(hours=2)
    add_todo(
        client, space["id"], title="OnlyBob", due_at=iso(due),
        reminders=[iso(due - timedelta(hours=1))], assignee_id=bob["id"],
    )
    backdate_reminders()
    assert tick() == 1
    ana_items = client.get("/api/notifications").json()["items"]
    assert not any(i["type"] == "reminder" for i in ana_items)
    bob_items = bob_c.get("/api/notifications").json()["items"]
    assert any(i["type"] == "reminder" for i in bob_items)


def test_unassigned_reminder_targets_all_members(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")

    due = datetime.now(UTC) + timedelta(hours=2)
    add_todo(client, space["id"], title="Everyone", due_at=iso(due), reminders=[iso(due - timedelta(hours=1))])
    backdate_reminders()
    assert tick() == 1
    for c in (client, bob_c):
        assert any(i["type"] == "reminder" for i in c.get("/api/notifications").json()["items"])


def test_completed_todo_reminder_claims_without_notifying(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    due = datetime.now(UTC) + timedelta(hours=2)
    todo = add_todo(client, space["id"], due_at=iso(due), reminders=[iso(due - timedelta(hours=1))])
    client.post(f"/api/todos/{todo['id']}/complete")
    backdate_reminders()
    tick()
    assert client.get("/api/notifications").json()["items"] == []
    assert tick() == 0


def test_gone_subscription_is_deleted(client, monkeypatch):
    from pywebpush import WebPushException

    from app.services import notify

    class FakeResp:
        status_code = 410

    def gone_webpush(subscription_info, data, **kwargs):
        raise WebPushException("gone", response=FakeResp())

    monkeypatch.setattr(notify, "webpush", gone_webpush)

    make_user(client, "ana@example.com")
    space = create_space(client)
    client.post(
        "/api/push/subscriptions",
        json={"endpoint": "https://push.example.com/dead", "keys": {"p256dh": "k", "auth": "a"}},
    )
    due = datetime.now(UTC) + timedelta(hours=2)
    add_todo(client, space["id"], due_at=iso(due), reminders=[iso(due - timedelta(hours=1))])
    backdate_reminders()
    tick()
    with test_engine().begin() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM push_subscriptions")).scalar() == 0


def test_flaky_subscription_deleted_after_five_failures(client, monkeypatch):
    from pywebpush import WebPushException

    from app.services import notify

    def flaky_webpush(subscription_info, data, **kwargs):
        raise WebPushException("boom", response=None)

    monkeypatch.setattr(notify, "webpush", flaky_webpush)

    make_user(client, "ana@example.com")
    space = create_space(client)
    client.post(
        "/api/push/subscriptions",
        json={"endpoint": "https://push.example.com/flaky", "keys": {"p256dh": "k", "auth": "a"}},
    )
    due = datetime.now(UTC) + timedelta(hours=6)
    for i in range(5):
        add_todo(client, space["id"], title=f"t{i}", due_at=iso(due), reminders=[iso(due - timedelta(hours=1))])
        backdate_reminders()
        tick()
    with test_engine().begin() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM push_subscriptions")).scalar() == 0
