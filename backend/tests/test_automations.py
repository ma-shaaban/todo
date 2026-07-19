"""Space automations + the Islamic-prayers provider (AlAdhan mocked)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.test_spaces import create_space, invite_code, make_user

UTC = timezone.utc
CAIRO = ZoneInfo("Africa/Cairo")

TIMES = {"Fajr": "04:30", "Dhuhr": "13:00", "Asr": "16:30", "Maghrib": "19:55", "Isha": "21:25"}


@pytest.fixture
def fake_aladhan(monkeypatch):
    """Serve fixed Cairo timings for tomorrow (all prayers in the future,
    so reminder creation is deterministic: two per prayer)."""
    from app.services.automations import prayers

    state = {
        "date": (datetime.now(UTC) + timedelta(days=1)).date(),
        "times": dict(TIMES),
        "calls": 0,
    }

    def fake(city, country, method):
        state["calls"] += 1
        return {"date": state["date"], "tz": CAIRO, "times": dict(state["times"])}

    monkeypatch.setattr(prayers, "fetch_timings", fake)
    return state


def enable(c, space_id, **cfg):
    body = {"type": "islamic_prayers", "config": {"city": "Cairo", "country": "Egypt", **cfg}}
    return c.put(f"/api/spaces/{space_id}/automation", json=body)


def test_enable_creates_five_group_todos(client, fake_aladhan):
    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    r = enable(client, space["id"], method=5)
    assert r.status_code == 200, r.text
    assert r.json()["automation"]["config"]["city"] == "Cairo"

    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    assert sorted(t["title"] for t in items) == sorted(TIMES)
    for t in items:
        assert t["completion_mode"] == "each"
        assert len(t["assignees"]) == 1
        assert len(t["reminders"]) == 2  # 15 min before + at prayer time
    fajr = next(t for t in items if t["title"] == "Fajr")
    day = fake_aladhan["date"]
    expected = datetime(day.year, day.month, day.day, 4, 30, tzinfo=CAIRO).astimezone(UTC)
    assert fajr["due_at"] == expected.isoformat()
    lead = min(r["remind_at"] for r in fajr["reminders"])
    assert lead == (expected - timedelta(minutes=15)).isoformat()

    # The space now advertises its automation.
    assert client.get(f"/api/spaces/{space['id']}").json()["automation"]["type"] == "islamic_prayers"


def test_tick_is_idempotent(client, fake_aladhan):
    from app.services.scheduler import automation_tick_once

    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    enable(client, space["id"])
    assert automation_tick_once() == 1
    assert automation_tick_once() == 1
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    assert len(items) == 5


def test_winter_timezone_conversion(client, fake_aladhan):
    # Next January: Egypt runs UTC+2 (no DST), so 04:30 local = 02:30Z.
    today = datetime.now(UTC)
    fake_aladhan["date"] = datetime(today.year + 1, 1, 15).date()
    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    enable(client, space["id"])
    fajr = next(
        t
        for t in client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
        if t["title"] == "Fajr"
    )
    assert fajr["due_at"].endswith("+00:00")
    assert "02:30" in fajr["due_at"]


def test_new_member_gets_future_prayers(client, make_client, fake_aladhan):
    from app.services.scheduler import automation_tick_once

    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    enable(client, space["id"])
    code = invite_code(client, space["id"])
    bob_c = make_client()
    make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")

    automation_tick_once()
    items = bob_c.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    # Tomorrow's prayers are all in the future → Bob gets a box on all 5.
    assert all(len(t["assignees"]) == 2 for t in items)
    # And they show up in his My Tasks.
    assert len(bob_c.get("/api/me/todos").json()["items"]) == 5


def test_retention_cleans_old_prayers(client, fake_aladhan):
    import sqlalchemy as sa

    from app.services.scheduler import automation_tick_once
    from tests.conftest import test_engine

    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    enable(client, space["id"])
    # Age one of the five well past retention.
    with test_engine().begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE todos SET due_at = now() - interval '8 days', "
                "automation_key = 'prayer:2026-07-01:fajr' "
                "WHERE title = 'Fajr'"
            )
        )
    automation_tick_once()
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    # The aged Fajr is gone; the tick re-created tomorrow's Fajr → still 5.
    assert sorted(t["title"] for t in items) == sorted(TIMES)
    assert not any(t["id"] == "prayer:2026-07-01:fajr" for t in items)


def test_automation_permissions_and_validation(client, make_client, fake_aladhan):
    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    code = invite_code(client, space["id"])
    bob_c = make_client()
    make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")
    stranger = make_client()
    make_user(stranger, "eve@example.com")

    assert enable(bob_c, space["id"]).status_code == 403
    assert enable(stranger, space["id"]).status_code == 404
    assert bob_c.delete(f"/api/spaces/{space['id']}/automation").status_code == 403

    bad_type = client.put(
        f"/api/spaces/{space['id']}/automation", json={"type": "weather", "config": {}}
    )
    assert bad_type.status_code == 400
    assert enable(client, space["id"], city="").status_code == 400
    assert enable(client, space["id"], method="five").status_code == 400
    assert enable(client, space["id"], method=99).status_code == 400

    # Disable keeps existing todos but clears the config.
    assert enable(client, space["id"]).status_code == 200
    assert client.delete(f"/api/spaces/{space['id']}/automation").status_code == 200
    detail = client.get(f"/api/spaces/{space['id']}").json()
    assert detail["automation"] is None
    assert len(client.get(f"/api/spaces/{space['id']}/todos").json()["items"]) == 5


def test_space_templates_listing(client):
    make_user(client, "ana@example.com")
    r = client.get("/api/space-templates")
    assert r.status_code == 200
    tpl = r.json()["items"][0]
    assert tpl["key"] == "islamic_prayers"
    assert tpl["default_space_name"] == "Prayer"
    assert {f["key"] for f in tpl["config_fields"]} == {"city", "country", "method"}


def test_create_space_from_template(client, fake_aladhan):
    make_user(client, "ana@example.com")
    r = client.post(
        "/api/spaces",
        json={
            "name": "Prayer",
            "template": "islamic_prayers",
            "config": {"city": "Cairo", "country": "Egypt", "method": 5},
        },
    )
    assert r.status_code == 201, r.text
    space = r.json()
    assert space["automation"]["type"] == "islamic_prayers"
    assert space["automation"]["config"]["city"] == "Cairo"
    # The immediate run populated the space before the first visit.
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    assert sorted(t["title"] for t in items) == sorted(TIMES)
    assert client.get(f"/api/spaces/{space['id']}").json()["automation"]["type"] == "islamic_prayers"


def test_create_space_template_validation(client, fake_aladhan, monkeypatch):
    from app.services.automations import prayers

    make_user(client, "ana@example.com")
    assert (
        client.post("/api/spaces", json={"name": "X", "template": "weather"}).status_code == 400
    )
    assert (
        client.post(
            "/api/spaces",
            json={"name": "X", "template": "islamic_prayers", "config": {"country": "Egypt"}},
        ).status_code
        == 400
    )

    def boom(city, country, method):
        raise RuntimeError("aladhan down")

    monkeypatch.setattr(prayers, "fetch_timings", boom)
    r = client.post(
        "/api/spaces",
        json={
            "name": "X",
            "template": "islamic_prayers",
            "config": {"city": "Cairo", "country": "Egypt"},
        },
    )
    assert r.status_code == 400
    # No half-created spaces leak from rejected template creates.
    assert client.get("/api/spaces").json()["items"] == []


def test_aladhan_failure_handling(client, fake_aladhan, monkeypatch):
    from app.services.automations import prayers
    from app.services.scheduler import automation_tick_once

    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    assert enable(client, space["id"]).status_code == 200  # healthy config saved

    def boom(city, country, method):
        raise RuntimeError("aladhan down")

    monkeypatch.setattr(prayers, "fetch_timings", boom)
    # An outage after enabling: the tick is contained, existing todos stay.
    assert automation_tick_once() == 0
    assert len(client.get(f"/api/spaces/{space['id']}/todos").json()["items"]) == 5
    # A config whose very first fetch fails is rejected up front — never
    # saved as an "On" card that silently does nothing forever.
    space2 = create_space(client, "Prayer2")
    assert enable(client, space2["id"]).status_code == 400
    assert client.get(f"/api/spaces/{space2['id']}").json()["automation"] is None


def test_past_midnight_isha_rolls_to_next_day(client, fake_aladhan):
    # High-latitude summer: Isha lands past midnight as a bare "00:32" —
    # earlier than Maghrib on the clock, but actually the NEXT local day.
    fake_aladhan["times"]["Maghrib"] = "23:12"
    fake_aladhan["times"]["Isha"] = "00:32"
    make_user(client, "ana@example.com")
    space = create_space(client, "Prayer")
    enable(client, space["id"])
    items = client.get(f"/api/spaces/{space['id']}/todos").json()["items"]
    maghrib = next(t for t in items if t["title"] == "Maghrib")
    isha = next(t for t in items if t["title"] == "Isha")
    assert isha["due_at"] > maghrib["due_at"]
    day = fake_aladhan["date"]
    expected = datetime(day.year, day.month, day.day, 0, 32, tzinfo=CAIRO) + timedelta(days=1)
    assert isha["due_at"] == expected.astimezone(UTC).isoformat()
