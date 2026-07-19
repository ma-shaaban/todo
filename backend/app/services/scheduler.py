"""Reminder poller: claims due reminders atomically and delivers them.

Runs as an asyncio task in the FastAPI lifespan (single replica). The claim
is an UPDATE … RETURNING, so even if replicas ever scale, a reminder fires
exactly once."""

import asyncio
import logging

import sqlalchemy as sa
from sqlalchemy.orm import Session as OrmSession

log = logging.getLogger("scheduler")

TICK_SECONDS = 30.0


def tick_once() -> int:
    """Claim and fire due reminders. Returns the number delivered. Sync —
    call from a worker thread."""
    from app import models
    from app.db import get_engine
    from app.services.notify import notify_users

    fired = 0
    with OrmSession(get_engine()) as db:
        claimed = db.execute(
            sa.text(
                "UPDATE reminders SET fired_at = now() "
                "WHERE fired_at IS NULL AND remind_at <= now() "
                "RETURNING todo_id"
            )
        ).all()
        db.commit()
        for (todo_id,) in claimed:
            todo = db.get(models.Todo, todo_id)
            if todo is None or todo.completed_at is not None:
                continue  # claimed so it never re-fires, but nothing to say
            if todo.assignee_id:
                targets = [todo.assignee_id]
            else:
                targets = [
                    m.user_id
                    for m in db.query(models.SpaceMember)
                    .filter(models.SpaceMember.space_id == todo.space_id)
                    .all()
                ]
            due_text = "This todo is due" if todo.due_at is None else "Don't forget this todo"
            notify_users(
                db,
                targets,
                type="reminder",
                title=f"⏰ {todo.title}",
                body=due_text,
                space_id=todo.space_id,
                todo_id=todo.id,
                url=f"/spaces/{todo.space_id}?todo={todo.id}",
            )
            fired += 1
        db.commit()
    return fired


async def run_poller(stop: asyncio.Event, interval: float = TICK_SECONDS) -> None:
    log.info("reminder poller started (every %ss)", interval)
    while not stop.is_set():
        try:
            await asyncio.to_thread(tick_once)
        except Exception:
            log.exception("reminder tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
    log.info("reminder poller stopped")
