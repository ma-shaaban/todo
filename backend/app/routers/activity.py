"""Per-space activity feed."""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership, parse_uuid

router = APIRouter(prefix="/api", tags=["activity"])

_LIST_CAP = 50


@router.get("/spaces/{space_id}/activity")
def space_activity(
    space_id: str,
    user: CurrentUser,
    db: DbSession,
    before: str | None = None,
    limit: int = _LIST_CAP,
):
    sid = parse_uuid(space_id)
    get_membership(db, sid, user)
    limit = max(1, min(limit, _LIST_CAP))
    q = db.query(models.Activity).filter(models.Activity.space_id == sid)
    if before:
        try:
            # An unencoded '+00:00' offset arrives as ' 00:00' — repair it.
            q = q.filter(
                models.Activity.created_at < datetime.fromisoformat(before.replace(" ", "+"))
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'before' timestamp")
    items = q.order_by(models.Activity.created_at.desc()).limit(limit).all()
    actor_ids = {a.actor_id for a in items if a.actor_id}
    actors = (
        {u.id: u for u in db.query(models.User).filter(models.User.id.in_(actor_ids)).all()}
        if actor_ids
        else {}
    )
    return {
        "items": [
            {
                "id": str(a.id),
                "type": a.type,
                "actor": (
                    {"id": str(a.actor_id), "display_name": actors[a.actor_id].display_name}
                    if a.actor_id in actors
                    else None
                ),
                "todo_id": str(a.todo_id) if a.todo_id else None,
                "data": a.data,
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ]
    }
