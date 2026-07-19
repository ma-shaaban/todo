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

# Space-template metadata: the create-space UI renders this generically
# (fields, defaults, options), so a new automation ships its own template
# with zero frontend changes.
TEMPLATE = {
    "key": "islamic_prayers",
    "icon": "🕌",
    "name": "Prayer space",
    "description": (
        "The five daily prayers appear automatically for everyone to check "
        "off — each person their own — with reminders 15 minutes before and "
        "at prayer time."
    ),
    "default_space_name": "Prayer",
    "config_fields": [
        {"key": "city", "label": "City", "type": "text", "default": "Cairo"},
        {"key": "country", "label": "Country", "type": "text", "default": "Egypt"},
        {
            "key": "method",
            "label": "Calculation method",
            "type": "select",
            "default": 5,
            "options": [
                {"value": 5, "label": "Egyptian General Authority"},
                {"value": 4, "label": "Umm Al-Qura (Makkah)"},
                {"value": 3, "label": "Muslim World League"},
                {"value": 2, "label": "ISNA (North America)"},
                {"value": 1, "label": "University of Karachi"},
                {"value": 8, "label": "Gulf Region"},
                {"value": 13, "label": "Diyanet (Turkey)"},
                {"value": None, "label": "Automatic"},
            ],
        },
    ],
}

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
    # follow_redirects: the dateless request 302s to the dated URL (AlAdhan
    # resolves "today" in the LOCATION's timezone — exactly what we want;
    # computing the date server-side in UTC would mis-key east-of-UTC cities
    # around midnight). httpx neither follows nor tolerates 3xx by default,
    # so without this every single call fails.
    resp = httpx.get(
        "https://api.aladhan.com/v1/timingsByCity",
        params=params,
        timeout=10,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    day, month, year = data["date"]["gregorian"]["date"].split("-")  # DD-MM-YYYY
    return {
        "date": datetime(int(year), int(month), int(day)).date(),
        "tz": ZoneInfo(data["meta"]["timezone"]),
        "times": {p: data["timings"][p] for p in PRAYERS},
    }


_MAX_CONFIG_STR = 100
_METHODS = set(range(0, 24))


def validate_config(cfg: dict) -> dict:
    """Normalized config, or ValueError with a user-facing message. Probes
    the real API once so a location that can't work is rejected up front
    instead of failing invisibly on every tick."""
    city = str(cfg.get("city") or "").strip()
    country = str(cfg.get("country") or "").strip()
    if not city or not country:
        raise ValueError("Please set a city and a country")
    if len(city) > _MAX_CONFIG_STR or len(country) > _MAX_CONFIG_STR:
        raise ValueError("City/country names are too long")
    method = cfg.get("method")
    if method is not None:
        if not isinstance(method, int) or isinstance(method, bool) or method not in _METHODS:
            raise ValueError("Unknown calculation method")
    try:
        fetch_timings(city, country, method)
    except Exception:
        raise ValueError(
            "Couldn't fetch prayer times for that location — check the "
            "city and country (or try again in a minute)"
        )
    return {"city": city, "country": country, "method": method}


def _parse_local(hhmm: str, day, tz) -> datetime | None:
    m = _TIME_RE.match(hhmm.strip())
    if not m:
        return None
    local = datetime(day.year, day.month, day.day, int(m.group(1)), int(m.group(2)), tzinfo=tz)
    return local.astimezone(timezone.utc)


def run(db, space, now) -> None:
    import sqlalchemy as sa

    cfg = space.automation_config or {}
    city = cfg.get("city") or "Cairo"
    country = cfg.get("country") or "Egypt"
    method = cfg.get("method")

    # Cheap pre-check only — the authoritative member read happens under
    # the space lock below, AFTER the network call.
    if (
        db.query(models.SpaceMember)
        .filter(models.SpaceMember.space_id == space.id)
        .first()
        is None
    ):
        return

    fetched = fetch_timings(city, country, method)
    day, tz = fetched["date"], fetched["tz"]

    # Serialize against member removal (which takes the same space lock):
    # a member kicked during the seconds-long AlAdhan call must not be
    # resurrected onto prayer todos from a stale member list. The lock is
    # taken only after the network call, so it's held briefly.
    db.execute(
        sa.select(models.Space.id).where(models.Space.id == space.id).with_for_update()
    ).first()
    member_ids = [
        m.user_id
        for m in db.query(models.SpaceMember)
        .filter(models.SpaceMember.space_id == space.id)
        .all()
    ]
    if not member_ids:
        return

    # Parse with midnight rollover: high-latitude Isha can land past
    # midnight (Reykjavik in July: Maghrib 23:12, Isha "00:32") — a bare
    # HH:MM earlier than the previous prayer means the NEXT local day.
    due_times: dict[str, datetime] = {}
    prev = None
    for prayer in PRAYERS:
        due_at = _parse_local(fetched["times"][prayer], day, tz)
        if due_at is None:
            log.warning(
                "unparseable %s time %r for space %s", prayer, fetched["times"][prayer], space.id
            )
            continue
        if prev is not None and due_at < prev:
            due_at += timedelta(days=1)
        due_times[prayer] = due_at
        prev = due_at

    existing = {
        t.automation_key: t
        for t in db.query(models.Todo)
        .filter(
            models.Todo.space_id == space.id,
            models.Todo.automation_key.startswith(f"{KEY_PREFIX}{day.isoformat()}:"),
        )
        .all()
    }
    for prayer, due_at in due_times.items():
        key = f"{KEY_PREFIX}{day.isoformat()}:{prayer.lower()}"
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
            # member-removal path.) Inserting an unchecked row races the
            # last checker's roll-up count, so honor the house invariant:
            # take the todo row lock, then re-check completion.
            db.execute(
                sa.select(models.Todo.id).where(models.Todo.id == todo.id).with_for_update()
            ).first()
            db.refresh(todo)
            if todo.completed_at is not None:
                continue
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
