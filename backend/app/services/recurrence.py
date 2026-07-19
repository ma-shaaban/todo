"""Recurring-todo date math. Pure functions, UTC-aware datetimes in/out."""

import calendar
from datetime import datetime, timedelta


def add_months(dt: datetime, months: int, anchor_day: int | None = None) -> datetime:
    """Same wall-clock time N months later. The day is the series' anchor day
    (falling back to dt's day), clamped to the target month's length — so a
    Jan-31 series hits Feb 28 but returns to Mar 31 instead of drifting to
    the 28th forever."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor_day or dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


_STEPS = {
    "daily": lambda d, a: d + timedelta(days=1),
    "weekly": lambda d, a: d + timedelta(weeks=1),
    "monthly": lambda d, a: add_months(d, 1, a),
}

RECURRENCES = tuple(_STEPS)


def next_due(
    due_at: datetime, recurrence: str, now: datetime, anchor_day: int | None = None
) -> datetime:
    """The next occurrence strictly in the future — a todo completed after
    sitting overdue for weeks doesn't spawn a pile of already-late copies."""
    step = _STEPS[recurrence]
    nxt = step(due_at, anchor_day)
    while nxt <= now:
        nxt = step(nxt, anchor_day)
    return nxt
