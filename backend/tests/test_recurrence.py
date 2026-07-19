from datetime import datetime, timedelta, timezone

from app.services.recurrence import add_months, next_due

UTC = timezone.utc


def dt(*args):
    return datetime(*args, tzinfo=UTC)


def test_add_months_clamps_to_month_end():
    assert add_months(dt(2026, 1, 31, 9, 0), 1) == dt(2026, 2, 28, 9, 0)
    assert add_months(dt(2024, 1, 31, 9, 0), 1) == dt(2024, 2, 29, 9, 0)  # leap year
    assert add_months(dt(2026, 3, 31, 9, 0), 1) == dt(2026, 4, 30, 9, 0)


def test_add_months_rolls_over_year():
    assert add_months(dt(2026, 12, 15, 8, 30), 1) == dt(2027, 1, 15, 8, 30)


def test_next_due_daily_skips_past_intervals():
    now = dt(2026, 7, 19, 12, 0)
    overdue = now - timedelta(days=10)
    nxt = next_due(overdue, "daily", now)
    assert nxt > now
    assert nxt - now <= timedelta(days=1)
    assert nxt.hour == overdue.hour and nxt.minute == overdue.minute


def test_next_due_weekly_and_monthly():
    now = dt(2026, 7, 19, 12, 0)
    due = dt(2026, 7, 18, 9, 0)
    assert next_due(due, "weekly", now) == dt(2026, 7, 25, 9, 0)
    assert next_due(due, "monthly", now) == dt(2026, 8, 18, 9, 0)


def test_next_due_future_due_advances_once():
    now = dt(2026, 7, 19, 12, 0)
    due = dt(2026, 7, 20, 9, 0)
    assert next_due(due, "daily", now) == dt(2026, 7, 21, 9, 0)
