"""In-app notification list + read state."""

import uuid

from fastapi import APIRouter, HTTPException

from app import models
from app.db import utcnow
from app.deps import CurrentUser, DbSession

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

_LIST_CAP = 50


@router.get("")
def list_notifications(user: CurrentUser, db: DbSession, unread: int = 0, limit: int = _LIST_CAP):
    limit = max(1, min(limit, _LIST_CAP))
    q = db.query(models.Notification).filter(models.Notification.user_id == user.id)
    if unread:
        q = q.filter(models.Notification.read_at.is_(None))
    items = q.order_by(models.Notification.created_at.desc()).limit(limit).all()
    unread_count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id, models.Notification.read_at.is_(None))
        .count()
    )
    return {
        "items": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "url": n.url,
                "space_id": str(n.space_id) if n.space_id else None,
                "todo_id": str(n.todo_id) if n.todo_id else None,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in items
        ],
        "unread_count": unread_count,
    }


@router.post("/read-all")
def read_all(user: CurrentUser, db: DbSession):
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id, models.Notification.read_at.is_(None)
    ).update({"read_at": utcnow()})
    return {"ok": True}


@router.post("/{notification_id}/read")
def read_one(notification_id: str, user: CurrentUser, db: DbSession):
    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    n = db.get(models.Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    if n.read_at is None:
        n.read_at = utcnow()
    return {"ok": True}
