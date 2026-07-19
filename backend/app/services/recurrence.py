"""Recurring-todo date math. Pure functions, UTC-aware datetimes in/out."""

import calendar
from datetime import datetime, timedelta


def add_months(dt: datetime, months: int) -> datetime:
    """Same wall-clock time N months later, day clamped to the target
    month's length (Jan 31 + 1mo → Feb 28/29)."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


_STEPS = {
    "daily": lambda d: d + timedelta(days=1),
    "weekly": lambda d: d + timedelta(weeks=1),
    "monthly": lambda d: add_months(d, 1),
}

RECURRENCES = tuple(_STEPS)


def next_due(due_at: datetime, recurrence: str, now: datetime) -> datetime:
    """The next occurrence strictly in the future — a todo completed after
    sitting overdue for weeks doesn't spawn a pile of already-late copies."""
    step = _STEPS[recurrence]
    nxt = step(due_at)
    while nxt <= now:
        nxt = step(nxt)
    return nxt
