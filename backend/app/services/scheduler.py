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
                if todo.completion_mode == "each":
                    # Nag only the people who haven't checked their box yet.
                    targets = [
                        row.user_id
                        for row in db.query(models.TodoAssignee)
                        .filter(
                            models.TodoAssignee.todo_id == todo.id,
                            models.TodoAssignee.completed_at.is_(None),
                        )
                        .all()
                    ]
                    if not targets:
                        continue
                elif todo.assignee_id:
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


# ── Space automations ─────────────────────────────────────────────────────

AUTOMATION_TICK_SECONDS = 15 * 60.0


def automation_tick_once() -> int:
    """Run every configured space's automation provider. Each space commits
    (or rolls back) independently — one broken space or one AlAdhan outage
    must not starve the rest. Sync — call from a worker thread."""
    from app import models
    from app.db import get_engine, utcnow
    from app.services.automations import PROVIDERS

    ran = 0
    with OrmSession(get_engine()) as db:
        space_ids = [
            row[0]
            for row in db.query(models.Space.id)
            .filter(models.Space.automation_type.is_not(None))
            .all()
        ]
    for sid in space_ids:
        with OrmSession(get_engine()) as db:
            try:
                space = db.get(models.Space, sid)
                if space is None:
                    continue
                provider = PROVIDERS.get(space.automation_type)
                if provider is None:
                    log.warning("unknown automation %r on space %s", space.automation_type, sid)
                    continue
                provider(db, space, utcnow())
                db.commit()
                ran += 1
            except Exception:
                log.exception("automation failed for space %s", sid)
    return ran


async def run_automations(stop: asyncio.Event, interval: float = AUTOMATION_TICK_SECONDS) -> None:
    """First tick immediately (todos should exist right after boot/enable),
    then every `interval`."""
    log.info("automation runner started (every %ss)", interval)
    while not stop.is_set():
        try:
            await asyncio.to_thread(automation_tick_once)
        except Exception:
            log.exception("automation tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
    log.info("automation runner stopped")
