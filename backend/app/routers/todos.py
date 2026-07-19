"""Todos: CRUD, completion (with recurring spawn), reminders, my-tasks."""

import math
import uuid
from datetime import timedelta, timezone

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy.exc import IntegrityError

from app import models
from app.db import utcnow
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership, parse_uuid
from app.schemas import TodoCreate, TodoPatch
from app.services.activity import record
from app.services.recurrence import RECURRENCES, next_due

router = APIRouter(prefix="/api", tags=["todos"])

_MAX_TITLE = 500
_MAX_NOTES = 5000
_MAX_REMINDERS = 20
_DONE_CAP = 200
_OPEN_CAP = 500


# ── validation helpers ────────────────────────────────────────────────────


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Please enter a title")
    if len(title) > _MAX_TITLE:
        raise HTTPException(status_code=400, detail=f"Title must be at most {_MAX_TITLE} characters")
    return title


def _clean_notes(notes: str) -> str:
    if len(notes) > _MAX_NOTES:
        raise HTTPException(status_code=400, detail=f"Notes must be at most {_MAX_NOTES} characters")
    return notes


def _clean_priority(priority: int) -> int:
    if not 0 <= priority <= 3:
        raise HTTPException(status_code=400, detail="Priority must be between 0 and 3")
    return priority


def _clean_position(position: float) -> float:
    # JSON NaN/Infinity survive parsing but crash response serialization.
    if not math.isfinite(position):
        raise HTTPException(status_code=400, detail="Position must be a finite number")
    return position


def _clean_recurrence(recurrence: str | None) -> str | None:
    if recurrence is not None and recurrence not in RECURRENCES:
        raise HTTPException(
            status_code=400, detail=f"Repeat must be one of: {', '.join(RECURRENCES)}"
        )
    return recurrence


def _aware(dt):
    """Naive datetimes are treated as UTC (JS clients always send Z)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _clean_assignee(db, space_id, assignee_id: str | None):
    if assignee_id is None:
        return None
    try:
        aid = uuid.UUID(assignee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown assignee")
    if db.get(models.SpaceMember, (space_id, aid)) is None:
        raise HTTPException(status_code=400, detail="The assignee must be a member of this space")
    return aid


def _clean_assignee_ids(db, space_id, assignee_ids: list[str]) -> list[uuid.UUID]:
    """Validated, deduped assignee set for an 'each' todo — all members."""
    ids: list[uuid.UUID] = []
    for raw in assignee_ids:
        try:
            aid = uuid.UUID(raw)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Unknown assignee")
        if aid not in ids:
            ids.append(aid)
    if not ids:
        raise HTTPException(
            status_code=400, detail="A shared-completion todo needs at least one assignee"
        )
    member_ids = {
        m.user_id
        for m in db.query(models.SpaceMember)
        .filter(models.SpaceMember.space_id == space_id, models.SpaceMember.user_id.in_(ids))
        .all()
    }
    if set(ids) - member_ids:
        raise HTTPException(status_code=400, detail="All assignees must be members of this space")
    return ids


def _no_unchecked_rows(db, todo_id) -> bool:
    return (
        db.query(models.TodoAssignee)
        .filter(
            models.TodoAssignee.todo_id == todo_id,
            models.TodoAssignee.completed_at.is_(None),
        )
        .count()
        == 0
    )


def roll_up_orphaned_each_todos(db, space_id, now) -> None:
    """After assignee rows vanish (member kicked/left): an open 'each' todo
    with ≥1 checked row and 0 unchecked rows can never complete through the
    normal path — finish it now. (No recurrence spawn: nobody acted.)
    Called by the spaces router inside its transaction."""
    orphans = (
        db.query(models.Todo.id)
        .filter(
            models.Todo.space_id == space_id,
            models.Todo.completion_mode == "each",
            models.Todo.completed_at.is_(None),
            sa.exists().where(
                models.TodoAssignee.todo_id == models.Todo.id,
                models.TodoAssignee.completed_at.is_not(None),
            ),
            ~sa.exists().where(
                models.TodoAssignee.todo_id == models.Todo.id,
                models.TodoAssignee.completed_at.is_(None),
            ),
        )
        .all()
    )
    for (tid,) in orphans:
        db.execute(
            sa.update(models.Todo)
            .where(models.Todo.id == tid, models.Todo.completed_at.is_(None))
            .values(completed_at=now, completed_by=None)
        )
    # A different orphan: the removed member held the ONLY rows and none
    # were checked, so nothing remains for anyone to check — an 'each' todo
    # with zero rows can never complete. Carry on as a normal shared todo.
    db.execute(
        sa.update(models.Todo)
        .where(
            models.Todo.space_id == space_id,
            models.Todo.completion_mode == "each",
            models.Todo.completed_at.is_(None),
            ~sa.exists().where(models.TodoAssignee.todo_id == models.Todo.id),
        )
        .values(completion_mode="any")
        .execution_options(synchronize_session=False)
    )


def _clean_reminders(reminders, now):
    if len(reminders) > _MAX_REMINDERS:
        raise HTTPException(status_code=400, detail=f"At most {_MAX_REMINDERS} reminders per todo")
    cleaned = []
    for r in reminders:
        r = _aware(r)
        if r <= now - timedelta(minutes=1):
            raise HTTPException(status_code=400, detail="Reminders must be in the future")
        cleaned.append(r)
    return cleaned


# ── serialization ─────────────────────────────────────────────────────────


def _todo_out(todo: models.Todo, users: dict, reminders: list, assignee_rows: list) -> dict:
    assignee = users.get(todo.assignee_id) if todo.assignee_id else None
    return {
        "id": str(todo.id),
        "space_id": str(todo.space_id),
        "title": todo.title,
        "notes": todo.notes,
        "due_at": todo.due_at.isoformat() if todo.due_at else None,
        "priority": todo.priority,
        "assignee": (
            {"id": str(assignee.id), "display_name": assignee.display_name} if assignee else None
        ),
        "completion_mode": todo.completion_mode,
        "assignees": [
            {
                "id": str(a.user_id),
                "display_name": users[a.user_id].display_name if a.user_id in users else "?",
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in assignee_rows
        ],
        "recurrence": todo.recurrence,
        "position": todo.position,
        "completed_at": todo.completed_at.isoformat() if todo.completed_at else None,
        "completed_by": str(todo.completed_by) if todo.completed_by else None,
        "created_by": str(todo.created_by) if todo.created_by else None,
        "created_at": todo.created_at.isoformat(),
        "reminders": [
            {
                "id": str(r.id),
                "remind_at": r.remind_at.isoformat(),
                "fired_at": r.fired_at.isoformat() if r.fired_at else None,
            }
            for r in reminders
        ],
    }


def _serialize_todos(db, todos: list) -> list[dict]:
    """Batch-load assignees + reminders (no N+1) and serialize."""
    if not todos:
        return []
    todo_ids = [t.id for t in todos]
    rows_by_todo: dict = {tid: [] for tid in todo_ids}
    for row in (
        db.query(models.TodoAssignee)
        .filter(models.TodoAssignee.todo_id.in_(todo_ids))
        .all()
    ):
        rows_by_todo[row.todo_id].append(row)
    user_ids = {t.assignee_id for t in todos if t.assignee_id}
    user_ids |= {row.user_id for rows in rows_by_todo.values() for row in rows}
    users = (
        {u.id: u for u in db.query(models.User).filter(models.User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )
    for rows in rows_by_todo.values():
        rows.sort(key=lambda r: users[r.user_id].display_name.lower() if r.user_id in users else "")
    reminders_by_todo: dict = {tid: [] for tid in todo_ids}
    for rem in (
        db.query(models.Reminder)
        .filter(models.Reminder.todo_id.in_(todo_ids))
        .order_by(models.Reminder.remind_at)
        .all()
    ):
        reminders_by_todo[rem.todo_id].append(rem)
    return [_todo_out(t, users, reminders_by_todo[t.id], rows_by_todo[t.id]) for t in todos]


def _notify_assignment(db, background: BackgroundTasks, todo: models.Todo, actor) -> None:
    if todo.assignee_id:
        assignee = db.get(models.User, todo.assignee_id)
        record(
            db, todo.space_id, actor, "todo_assigned", todo=todo,
            title=todo.title, assignee_name=assignee.display_name if assignee else "?",
        )
    if todo.assignee_id and todo.assignee_id != actor.id:
        from app.services.notify import notify_users, send_pushes

        prepared = notify_users(
            db,
            [todo.assignee_id],
            type="assigned",
            title=f"{actor.display_name} assigned you: {todo.title}",
            space_id=todo.space_id,
            todo_id=todo.id,
            url=f"/spaces/{todo.space_id}?todo={todo.id}",
        )
        # Network delivery only after this request's transaction commits.
        background.add_task(send_pushes, prepared)


def _get_todo_for_member(db, todo_id: str, user) -> models.Todo:
    tid = parse_uuid(todo_id)
    todo = db.get(models.Todo, tid)
    if todo is None:
        raise HTTPException(status_code=404, detail="Not found")
    get_membership(db, todo.space_id, user)  # 404 when not visible
    return todo


_OPEN_ORDER = (
    sa.nulls_last(sa.asc(models.Todo.due_at)),
    sa.desc(models.Todo.priority),
    sa.asc(models.Todo.position),
    sa.asc(models.Todo.created_at),
)


# ── endpoints ─────────────────────────────────────────────────────────────


@router.get("/spaces/{space_id}/todos")
def list_todos(space_id: str, user: CurrentUser, db: DbSession, status: str = "open"):
    sid = parse_uuid(space_id)
    get_membership(db, sid, user)
    q = db.query(models.Todo).filter(models.Todo.space_id == sid)
    if status == "open":
        q = q.filter(models.Todo.completed_at.is_(None)).order_by(*_OPEN_ORDER).limit(_OPEN_CAP)
    elif status == "done":
        q = (
            q.filter(models.Todo.completed_at.is_not(None))
            .order_by(sa.desc(models.Todo.completed_at))
            .limit(_DONE_CAP)
        )
    else:
        raise HTTPException(status_code=400, detail="status must be open or done")
    return {"items": _serialize_todos(db, q.all())}


@router.post("/spaces/{space_id}/todos", status_code=201)
def create_todo(
    space_id: str, body: TodoCreate, user: CurrentUser, db: DbSession, background: BackgroundTasks
):
    sid = parse_uuid(space_id)
    get_membership(db, sid, user)
    now = utcnow()
    due_at = _aware(body.due_at)
    recurrence = _clean_recurrence(body.recurrence)
    if recurrence and due_at is None:
        raise HTTPException(status_code=400, detail="Repeating todos need a due date")
    if body.completion_mode not in ("any", "each"):
        raise HTTPException(status_code=400, detail="completion_mode must be any or each")
    each_ids = (
        _clean_assignee_ids(db, sid, body.assignee_ids or [])
        if body.completion_mode == "each"
        else []
    )
    todo = models.Todo(
        space_id=sid,
        title=_clean_title(body.title),
        notes=_clean_notes(body.notes),
        due_at=due_at,
        priority=_clean_priority(body.priority),
        # 'each' keeps the legacy single-assignee slot empty; the set lives
        # in todo_assignees.
        assignee_id=None if each_ids else _clean_assignee(db, sid, body.assignee_id),
        completion_mode=body.completion_mode,
        recurrence=recurrence,
        recur_anchor_day=due_at.day if (recurrence == "monthly" and due_at) else None,
        position=_clean_position(body.position),
        created_by=user.id,
    )
    db.add(todo)
    reminders = _clean_reminders(body.reminders, now)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # The space was deleted between the membership check and the insert.
        raise HTTPException(status_code=404, detail="Not found")
    for aid in each_ids:
        db.add(models.TodoAssignee(todo_id=todo.id, user_id=aid))
    for remind_at in reminders:
        db.add(models.Reminder(todo_id=todo.id, remind_at=remind_at))
    db.flush()
    record(db, sid, user, "todo_created", todo=todo, title=todo.title)
    _notify_assignment(db, background, todo, user)
    return _serialize_todos(db, [todo])[0]


@router.patch("/todos/{todo_id}")
def patch_todo(
    todo_id: str, body: TodoPatch, user: CurrentUser, db: DbSession, background: BackgroundTasks
):
    todo = _get_todo_for_member(db, todo_id, user)
    fields = body.model_fields_set
    now = utcnow()

    if "title" in fields:
        if body.title is None:
            raise HTTPException(status_code=400, detail="Please enter a title")
        todo.title = _clean_title(body.title)
    if "notes" in fields:
        todo.notes = _clean_notes(body.notes or "")
    if "due_at" in fields:
        todo.due_at = _aware(body.due_at)
    if "priority" in fields:
        todo.priority = _clean_priority(body.priority if body.priority is not None else 0)
    if "assignee_id" in fields:
        if todo.completion_mode == "each":
            # The legacy single-assignee slot stays empty on group todos —
            # setting it would poison My Tasks and fire a false "assigned
            # you" push at someone who has no box to check. Explicit null
            # is tolerated (the editor always sends it).
            if body.assignee_id is not None:
                raise HTTPException(
                    status_code=400,
                    detail="This is a group todo — everyone assigned checks off their own",
                )
        else:
            previous_assignee = todo.assignee_id
            todo.assignee_id = _clean_assignee(db, todo.space_id, body.assignee_id)
            if todo.assignee_id and todo.assignee_id != previous_assignee:
                _notify_assignment(db, background, todo, user)
    if "recurrence" in fields:
        todo.recurrence = _clean_recurrence(body.recurrence)
    if "position" in fields and body.position is not None:
        todo.position = _clean_position(body.position)
    if todo.recurrence and todo.due_at is None:
        raise HTTPException(status_code=400, detail="Repeating todos need a due date")
    if "due_at" in fields or "recurrence" in fields:
        # Re-anchor the monthly series to the (possibly new) due day.
        todo.recur_anchor_day = (
            todo.due_at.day if (todo.recurrence == "monthly" and todo.due_at) else None
        )

    if "reminders" in fields:
        new_reminders = _clean_reminders(body.reminders or [], now)
        # Replace only the un-fired reminders; fired ones are history — but
        # the 20-reminder cap holds for the TOTAL per todo, not per request.
        fired_count = (
            db.query(models.Reminder)
            .filter(models.Reminder.todo_id == todo.id, models.Reminder.fired_at.is_not(None))
            .count()
        )
        if fired_count + len(new_reminders) > _MAX_REMINDERS:
            raise HTTPException(
                status_code=400, detail=f"At most {_MAX_REMINDERS} reminders per todo"
            )
        db.query(models.Reminder).filter(
            models.Reminder.todo_id == todo.id, models.Reminder.fired_at.is_(None)
        ).delete()
        for remind_at in new_reminders:
            db.add(models.Reminder(todo_id=todo.id, remind_at=remind_at))
    db.flush()
    return _serialize_todos(db, [todo])[0]


@router.delete("/todos/{todo_id}")
def delete_todo(todo_id: str, user: CurrentUser, db: DbSession):
    todo = _get_todo_for_member(db, todo_id, user)
    record(db, todo.space_id, user, "todo_deleted", title=todo.title)
    db.delete(todo)  # reminders cascade
    return {"ok": True}


@router.post("/todos/{todo_id}/complete")
def complete_todo(todo_id: str, user: CurrentUser, db: DbSession, background: BackgroundTasks):
    todo = _get_todo_for_member(db, todo_id, user)
    now = utcnow()

    if todo.completion_mode == "each":
        # Check off MY row; the parent completes only when the last row is
        # checked. The roll-up decision (count-then-claim) is write-skew
        # prone under READ COMMITTED — two "last" checkers would each see
        # the other's row still unchecked and BOTH skip the parent claim —
        # so every roll-up decision serializes on the parent todo row lock
        # (complete, reopen, and member-removal cleanup all take it).
        my_row = db.get(models.TodoAssignee, (todo.id, user.id))
        if my_row is None:
            raise HTTPException(
                status_code=400, detail="Only its assignees can check off this todo"
            )
        db.execute(
            sa.select(models.Todo.id).where(models.Todo.id == todo.id).with_for_update()
        ).first()
        row_claimed = db.execute(
            sa.update(models.TodoAssignee)
            .where(
                models.TodoAssignee.todo_id == todo.id,
                models.TodoAssignee.user_id == user.id,
                models.TodoAssignee.completed_at.is_(None),
            )
            .values(completed_at=now)
            .returning(models.TodoAssignee.user_id)
        ).first()
        if row_claimed is not None:
            record(db, todo.space_id, user, "todo_checked", todo=todo, title=todo.title)
        # Deliberately NOT gated on row_claimed: a tap from an already-
        # checked assignee re-evaluates the roll-up, healing any todo that
        # ended up all-checked-but-open.
        claimed = (
            db.execute(
                sa.update(models.Todo)
                .where(models.Todo.id == todo.id, models.Todo.completed_at.is_(None))
                .values(completed_at=now, completed_by=user.id)
                .returning(models.Todo.id)
            ).first()
            if _no_unchecked_rows(db, todo.id)
            else None
        )
        db.expire(todo)
    else:
        # Atomic claim: only one caller wins, so a double-tap can't
        # double-spawn the next occurrence of a recurring todo.
        claimed = db.execute(
            sa.update(models.Todo)
            .where(models.Todo.id == todo.id, models.Todo.completed_at.is_(None))
            .values(completed_at=now, completed_by=user.id)
            .returning(models.Todo.id)
        ).first()
        db.expire(todo)

    next_out = None
    if claimed is not None and todo.recurrence and todo.due_at:
        new_due = next_due(todo.due_at, todo.recurrence, now, todo.recur_anchor_day)
        nxt = models.Todo(
            space_id=todo.space_id,
            title=todo.title,
            notes=todo.notes,
            due_at=new_due,
            priority=todo.priority,
            assignee_id=todo.assignee_id,
            completion_mode=todo.completion_mode,
            recurrence=todo.recurrence,
            recur_anchor_day=todo.recur_anchor_day,
            spawned_from=todo.id,
            position=todo.position,
            created_by=todo.created_by,
        )
        db.add(nxt)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            # The space was deleted mid-flight; the completion stamp is gone
            # with it, so answer like any other vanished space.
            raise HTTPException(status_code=404, detail="Not found")
        # 'each' series: the next occurrence starts with everyone unchecked —
        # but only CURRENT members. A kicked member's checked row stays on
        # the old occurrence as history; cloning it would put an unchecked
        # box on the successor that nobody could ever check.
        if todo.completion_mode == "each":
            member_ids = {
                m.user_id
                for m in db.query(models.SpaceMember)
                .filter(models.SpaceMember.space_id == todo.space_id)
                .all()
            }
            cloned = 0
            for row in (
                db.query(models.TodoAssignee)
                .filter(models.TodoAssignee.todo_id == todo.id)
                .all()
            ):
                if row.user_id in member_ids:
                    db.add(models.TodoAssignee(todo_id=nxt.id, user_id=row.user_id))
                    cloned += 1
            if cloned == 0:
                # Every original assignee left the space: a rowless 'each'
                # todo is uncompletable — carry on as a normal shared todo.
                nxt.completion_mode = "any"
        # Clone ALL reminders (fired ones included — a fired reminder is
        # exactly the configuration the next occurrence needs) preserving
        # their offset from the due date; drop any landing in the past.
        for rem in (
            db.query(models.Reminder).filter(models.Reminder.todo_id == todo.id).all()
        ):
            shifted = new_due - (todo.due_at - rem.remind_at)
            if shifted > now:
                db.add(models.Reminder(todo_id=nxt.id, remind_at=shifted))
        db.flush()
        next_out = _serialize_todos(db, [nxt])[0]

    if claimed is not None:
        record(db, todo.space_id, user, "todo_completed", todo=todo, title=todo.title)
        from app.services.notify import notify_users, send_pushes

        each_ids = [
            row.user_id
            for row in db.query(models.TodoAssignee)
            .filter(models.TodoAssignee.todo_id == todo.id)
            .all()
        ]
        prepared = notify_users(
            db,
            [uid for uid in (todo.created_by, todo.assignee_id, *each_ids) if uid],
            type="completed",
            title=f"✅ {user.display_name} completed: {todo.title}",
            space_id=todo.space_id,
            todo_id=todo.id,
            url=f"/spaces/{todo.space_id}?todo={todo.id}",
            exclude=user.id,
        )
        background.add_task(send_pushes, prepared)

    return {"completed": _serialize_todos(db, [todo])[0], "next": next_out}


@router.post("/todos/{todo_id}/reopen")
def reopen_todo(todo_id: str, user: CurrentUser, db: DbSession):
    todo = _get_todo_for_member(db, todo_id, user)
    if todo.completion_mode == "each":
        my_row = db.get(models.TodoAssignee, (todo.id, user.id))
        if my_row is None:
            raise HTTPException(
                status_code=400, detail="Only its assignees can uncheck this todo"
            )
        # Same per-todo serialization as complete: unchecking while someone
        # else's roll-up is deciding must not complete a todo with a fresh
        # unchecked row. Refresh after the lock — the parent may have
        # completed while we waited.
        db.execute(
            sa.select(models.Todo.id).where(models.Todo.id == todo.id).with_for_update()
        ).first()
        db.refresh(todo)
        my_row.completed_at = None
        # Fall through: an accidentally-completed parent reopens (and its
        # recurrence successor is retracted) exactly like an 'any' todo.
        if todo.completed_at is None:
            db.flush()
            return _serialize_todos(db, [todo])[0]
    # Undo the recurrence spawn too: completing accidentally and reopening
    # must not leave a duplicate series. Only a still-open, un-completed
    # successor is retracted — one that was already completed is history.
    if todo.recurrence:
        db.query(models.Reminder).filter(
            models.Reminder.todo_id.in_(
                sa.select(models.Todo.id).where(
                    models.Todo.spawned_from == todo.id,
                    models.Todo.completed_at.is_(None),
                )
            )
        ).delete(synchronize_session=False)
        db.query(models.Todo).filter(
            models.Todo.spawned_from == todo.id, models.Todo.completed_at.is_(None)
        ).delete(synchronize_session=False)
    todo.completed_at = None
    todo.completed_by = None
    record(db, todo.space_id, user, "todo_reopened", todo=todo, title=todo.title)
    db.flush()
    return _serialize_todos(db, [todo])[0]


@router.get("/me/todos")
def my_todos(user: CurrentUser, db: DbSession):
    """Open todos across my spaces: assigned to me, or unassigned ones I
    created."""
    my_space_ids = [
        row[0]
        for row in db.query(models.SpaceMember.space_id)
        .filter(models.SpaceMember.user_id == user.id)
        .all()
    ]
    if not my_space_ids:
        return {"items": []}
    todos = (
        db.query(models.Todo)
        .filter(
            models.Todo.space_id.in_(my_space_ids),
            models.Todo.completed_at.is_(None),
            sa.or_(
                models.Todo.assignee_id == user.id,
                sa.and_(
                    models.Todo.assignee_id.is_(None),
                    models.Todo.completion_mode == "any",
                    models.Todo.created_by == user.id,
                ),
                # 'each' todos where MY check is still pending.
                sa.exists().where(
                    models.TodoAssignee.todo_id == models.Todo.id,
                    models.TodoAssignee.user_id == user.id,
                    models.TodoAssignee.completed_at.is_(None),
                ),
            ),
        )
        .order_by(*_OPEN_ORDER)
        .limit(_OPEN_CAP)
        .all()
    )
    spaces = {
        s.id: s
        for s in db.query(models.Space).filter(models.Space.id.in_(my_space_ids)).all()
    }
    items = _serialize_todos(db, todos)
    for item, todo in zip(items, todos):
        space = spaces.get(todo.space_id)
        item["space"] = {"id": str(todo.space_id), "name": space.name if space else ""}
    return {"items": items}
