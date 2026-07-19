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


_CLAIM_BATCH = 100


def tick_once() -> int:
    """Claim due reminders and create their notifications in ONE transaction
    (a crash rolls back the claim too — nothing is ever silently lost), then
    deliver web pushes after commit. Returns the number fired. Sync — call
    from a worker thread."""
    from app import models
    from app.db import get_engine
    from app.services.notify import notify_users, send_pushes

    fired = 0
    prepared: list[dict] = []
    with OrmSession(get_engine()) as db:
        claimed = db.execute(
            sa.text(
                "UPDATE reminders SET fired_at = now() WHERE id IN ("
                "  SELECT id FROM reminders"
                "  WHERE fired_at IS NULL AND remind_at <= now()"
                "  ORDER BY remind_at"
                f"  LIMIT {_CLAIM_BATCH}"
                "  FOR UPDATE SKIP LOCKED"
                ") RETURNING todo_id"
            )
        ).all()
        for (todo_id,) in claimed:
            try:
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
                prepared += notify_users(
                    db,
                    targets,
                    type="reminder",
                    title=f"⏰ {todo.title}",
                    body="Don't forget this todo",
                    space_id=todo.space_id,
                    todo_id=todo.id,
                    url=f"/spaces/{todo.space_id}?todo={todo.id}",
                )
                fired += 1
            except Exception:
                # One bad row must not sink the whole batch.
                log.exception("failed to prepare reminder for todo %s", todo_id)
        db.commit()  # claims + notification rows land atomically
    send_pushes(prepared)  # network I/O strictly after the transaction
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
