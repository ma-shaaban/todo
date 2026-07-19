"""In-app notifications + web push delivery.

Two-phase design: `notify_users` inserts notification rows inside the
caller's transaction and returns *prepared sends*; `send_pushes` does the
actual network delivery and must run AFTER that transaction commits
(FastAPI BackgroundTasks in request paths, post-commit in the poller).
Pushing before commit would notify people about actions that might roll
back — and a slow push service must never hold a DB transaction open."""

import json
import logging

from pywebpush import WebPushException, webpush  # noqa: F401 (tests monkeypatch module attr)
from sqlalchemy.orm import Session as OrmSession

from app import models
from app.services.vapid import get_vapid

log = logging.getLogger(__name__)

_MAX_FAILURES = 5
_SEND_TIMEOUT_SECONDS = 5
_TTL_REMINDER = 3600  # a late reminder is better than a dropped one…
_TTL_SOCIAL = 86400  # …and social events can wait a day for an offline phone


def notify_users(db, user_ids, *, type: str, title: str, body: str = "", url: str = "/",
                 space_id=None, todo_id=None, exclude=None) -> list[dict]:
    """Insert in-app notification rows (committed with the caller's
    transaction) and return prepared web-push sends for `send_pushes`."""
    targets = [uid for uid in set(user_ids) if uid != exclude]
    if not targets:
        return []
    for uid in targets:
        db.add(
            models.Notification(
                user_id=uid, type=type, title=title, body=body, url=url,
                space_id=space_id, todo_id=todo_id,
            )
        )
    db.flush()
    payload = json.dumps(
        {"title": title, "body": body, "url": url, "tag": f"{type}-{todo_id or space_id}"}
    )
    ttl = _TTL_REMINDER if type == "reminder" else _TTL_SOCIAL
    subs = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.user_id.in_(targets))
        .all()
    )
    return [
        {
            "id": str(s.id),
            "endpoint": s.endpoint,
            "p256dh": s.p256dh,
            "auth": s.auth,
            "payload": payload,
            "ttl": ttl,
        }
        for s in subs
    ]


def send_pushes(prepared: list[dict]) -> None:
    """Deliver prepared sends. Runs outside any request transaction; prunes
    dead/flaky subscriptions in its own session. Never raises."""
    if not prepared:
        return
    try:
        vapid = get_vapid()
    except Exception:
        log.exception("cannot load VAPID config — skipping %d pushes", len(prepared))
        return
    dead, flaky, ok = [], [], []
    for p in prepared:
        try:
            # Module-global lookup at call time — tests monkeypatch notify.webpush.
            webpush(
                subscription_info={
                    "endpoint": p["endpoint"],
                    "keys": {"p256dh": p["p256dh"], "auth": p["auth"]},
                },
                data=p["payload"],
                vapid_private_key=vapid["private"],
                vapid_claims={"sub": vapid["subject"]},
                ttl=p["ttl"],
                timeout=_SEND_TIMEOUT_SECONDS,
            )
            ok.append(p["id"])
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                dead.append(p["id"])  # browser dropped the subscription
            else:
                flaky.append(p["id"])
            log.warning("web push failed (status=%s endpoint=%s…)", status, p["endpoint"][:40])
        except Exception:
            log.exception("unexpected web push failure")
    if not (dead or flaky or ok):
        return
    try:
        import uuid as _uuid

        from app.db import get_engine

        with OrmSession(get_engine()) as db:
            if dead:
                db.query(models.PushSubscription).filter(
                    models.PushSubscription.id.in_([_uuid.UUID(i) for i in dead])
                ).delete(synchronize_session=False)
            for sid in flaky:
                sub = db.get(models.PushSubscription, _uuid.UUID(sid))
                if sub is not None:
                    sub.failed_count = (sub.failed_count or 0) + 1
                    if sub.failed_count >= _MAX_FAILURES:
                        db.delete(sub)
            for sid in ok:
                sub = db.get(models.PushSubscription, _uuid.UUID(sid))
                if sub is not None and sub.failed_count:
                    sub.failed_count = 0
            db.commit()
    except Exception:
        log.exception("push subscription bookkeeping failed")
