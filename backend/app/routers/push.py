"""Web-push subscription management."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import models
from app.deps import CurrentUser, DbSession
from app.services.vapid import get_vapid

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


class UnsubscribeIn(BaseModel):
    endpoint: str


@router.get("/vapid-public-key")
def vapid_public_key():
    return {"key": get_vapid()["public"]}


@router.post("/subscriptions", status_code=201)
def subscribe(body: SubscriptionIn, user: CurrentUser, db: DbSession):
    if len(body.endpoint) > 2000 or not body.endpoint.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid subscription endpoint")
    existing = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.endpoint == body.endpoint)
        .one_or_none()
    )
    if existing:
        # Same browser, possibly a different signed-in user now.
        existing.user_id = user.id
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        existing.failed_count = 0
    else:
        # Cap devices per user (oldest evicted): bounds table growth and the
        # outbound-request amplification any single account can cause.
        mine = (
            db.query(models.PushSubscription)
            .filter(models.PushSubscription.user_id == user.id)
            .order_by(models.PushSubscription.created_at.desc())
            .all()
        )
        for stale in mine[9:]:
            db.delete(stale)
        db.add(
            models.PushSubscription(
                user_id=user.id,
                endpoint=body.endpoint,
                p256dh=body.keys.p256dh,
                auth=body.keys.auth,
            )
        )
    return {"ok": True}


@router.delete("/subscriptions", status_code=204)
def unsubscribe(body: UnsubscribeIn, user: CurrentUser, db: DbSession):
    db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == body.endpoint,
        models.PushSubscription.user_id == user.id,
    ).delete()
    return Response(status_code=204)
