"""In-app notifications + web push delivery."""

import json
import logging

from pywebpush import WebPushException, webpush  # noqa: F401 (tests monkeypatch module attr)

from app import models
from app.services.vapid import get_vapid

log = logging.getLogger(__name__)

_MAX_FAILURES = 5


def notify_users(db, user_ids, *, type: str, title: str, body: str = "", url: str = "/",
                 space_id=None, todo_id=None, exclude=None) -> None:
    """Insert an in-app notification and push to every device of each user.
    Never raises — a notification failure must not fail the triggering action."""
    targets = [uid for uid in set(user_ids) if uid != exclude]
    if not targets:
        return
    for uid in targets:
        db.add(
            models.Notification(
                user_id=uid, type=type, title=title, body=body, url=url,
                space_id=space_id, todo_id=todo_id,
            )
        )
    db.flush()
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": f"{type}-{todo_id or space_id}"})
    subs = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.user_id.in_(targets))
        .all()
    )
    for sub in subs:
        _send_push(db, sub, payload)


def _send_push(db, sub: models.PushSubscription, payload: str) -> None:
    vapid = get_vapid()
    try:
        # Module-global lookup at call time — tests monkeypatch notify.webpush.
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=payload,
            vapid_private_key=vapid["private"],
            vapid_claims={"sub": vapid["subject"]},
        )
        if sub.failed_count:
            sub.failed_count = 0
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            # The browser dropped the subscription — clean up.
            db.delete(sub)
        else:
            sub.failed_count = (sub.failed_count or 0) + 1
            if sub.failed_count >= _MAX_FAILURES:
                db.delete(sub)
        log.warning("web push failed (status=%s endpoint=%s…)", status, sub.endpoint[:40])
    except Exception:
        log.exception("unexpected web push failure")
