"""Islamic prayer times automation (AlAdhan API).

Each tick creates today's five prayers as completion_mode='each' todos
assigned to every member — everyone checks off their own prayer — with
reminders 15 minutes before and at the prayer time. Missed prayers stay
visible (still checkable — qada) for RETENTION_DAYS, then are removed.
Config: {"city": "Cairo", "country": "Egypt", "method": 5} (method =
AlAdhan calculation method; 5 = Egyptian General Authority of Survey).
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from app import models

log = logging.getLogger(__name__)

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
KEY_PREFIX = "prayer:"
RETENTION_DAYS = 7
REMINDER_LEAD = timedelta(minutes=15)
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})")  # tolerate "04:30 (EEST)" suffixes


def fetch_timings(city: str, country: str, method: int | None) -> dict:
    """Today's timings at the location (AlAdhan resolves 'today' in the
    location's own timezone when no date is given). Returns
    {"date": date, "tz": ZoneInfo, "times": {prayer: "HH:MM"}}.
    Module-level so tests monkeypatch it."""
    params = {"city": city, "country": country}
    if method is not None:
        params["method"] = method
    resp = httpx.get(
        "https://api.aladhan.com/v1/timingsByCity", params=params, timeout=10
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    day, month, year = data["date"]["gregorian"]["date"].split("-")  # DD-MM-YYYY
    return {
        "date": datetime(int(year), int(month), int(day)).date(),
        "tz": ZoneInfo(data["meta"]["timezone"]),
        "times": {p: data["timings"][p] for p in PRAYERS},
    }


def _parse_local(hhmm: str, day, tz) -> datetime | None:
    m = _TIME_RE.match(hhmm.strip())
    if not m:
        return None
    local = datetime(day.year, day.month, day.day, int(m.group(1)), int(m.group(2)), tzinfo=tz)
    return local.astimezone(timezone.utc)


def run(db, space, now) -> None:
    cfg = space.automation_config or {}
    city = cfg.get("city") or "Cairo"
    country = cfg.get("country") or "Egypt"
    method = cfg.get("method")

    member_ids = [
        m.user_id
        for m in db.query(models.SpaceMember)
        .filter(models.SpaceMember.space_id == space.id)
        .all()
    ]
    if not member_ids:
        return

    fetched = fetch_timings(city, country, method)
    day, tz = fetched["date"], fetched["tz"]

    existing = {
        t.automation_key: t
        for t in db.query(models.Todo)
        .filter(
            models.Todo.space_id == space.id,
            models.Todo.automation_key.startswith(f"{KEY_PREFIX}{day.isoformat()}:"),
        )
        .all()
    }
    for prayer in PRAYERS:
        key = f"{KEY_PREFIX}{day.isoformat()}:{prayer.lower()}"
        due_at = _parse_local(fetched["times"][prayer], day, tz)
        if due_at is None:
            log.warning("unparseable %s time %r for space %s", prayer, fetched["times"][prayer], space.id)
            continue
        todo = existing.get(key)
        if todo is None:
            todo = models.Todo(
                space_id=space.id,
                title=prayer,
                notes=f"Prayer time in {city}",
                due_at=due_at,
                completion_mode="each",
                automation_key=key,
                created_by=None,
            )
            db.add(todo)
            db.flush()
            for uid in member_ids:
                db.add(models.TodoAssignee(todo_id=todo.id, user_id=uid))
            # A prayer created after its time has passed (automation just
            # enabled, or downtime) must not fire a stale "reminder" push.
            for remind_at in (due_at - REMINDER_LEAD, due_at):
                if remind_at > now:
                    db.add(models.Reminder(todo_id=todo.id, remind_at=remind_at))
        elif todo.completed_at is None and todo.due_at and todo.due_at > now:
            # Membership sync: whoever joined since creation gets a box on
            # prayers still ahead today. (Leavers are handled by the
            # member-removal path.)
            have = {
                r.user_id
                for r in db.query(models.TodoAssignee)
                .filter(models.TodoAssignee.todo_id == todo.id)
                .all()
            }
            for uid in set(member_ids) - have:
                db.add(models.TodoAssignee(todo_id=todo.id, user_id=uid))

    # Retention: this provider's todos vanish quietly after a week.
    cutoff = now - timedelta(days=RETENTION_DAYS)
    old = (
        db.query(models.Todo)
        .filter(
            models.Todo.space_id == space.id,
            models.Todo.automation_key.startswith(KEY_PREFIX),
            models.Todo.due_at < cutoff,
        )
        .all()
    )
    for t in old:
        db.delete(t)  # reminders + assignee rows cascade
