"""VAPID key management for web push.

Staging/prod: keys arrive as env vars from the platform's `app-push` Secret.
Local dev (no env): a keypair is generated once and persisted in app_meta so
push subscriptions stay valid across restarts."""

import logging
import os

import sqlalchemy as sa

log = logging.getLogger(__name__)

_cache: dict | None = None

_META_PUBLIC = "vapid_public_key"
_META_PRIVATE = "vapid_private_key"
_DEFAULT_SUBJECT = "https://todo.nezam.site"


def _generate() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid, b64urlencode

    v = Vapid()
    v.generate_keys()
    private = b64urlencode(v.private_key.private_numbers().private_value.to_bytes(32, "big"))
    public = b64urlencode(
        v.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    return public, private


def get_vapid() -> dict:
    """{'public': ..., 'private': ..., 'subject': ...} — env first, else
    app_meta bootstrap (race-safe via ON CONFLICT DO NOTHING + re-read)."""
    global _cache
    if _cache is not None:
        return _cache
    env_public = os.environ.get("VAPID_PUBLIC_KEY")
    env_private = os.environ.get("VAPID_PRIVATE_KEY")
    subject = os.environ.get("VAPID_SUBJECT", _DEFAULT_SUBJECT)
    if env_public and env_private:
        _cache = {"public": env_public, "private": env_private, "subject": subject}
        return _cache

    from app.db import get_engine

    with get_engine().begin() as conn:
        rows = dict(
            conn.execute(
                sa.text("SELECT key, value FROM app_meta WHERE key IN (:p, :s)"),
                {"p": _META_PUBLIC, "s": _META_PRIVATE},
            ).all()
        )
        if _META_PUBLIC not in rows or _META_PRIVATE not in rows:
            if rows:
                # Half a keypair is corruption — mixing halves of two pairs
                # would break every push silently. Start over.
                conn.execute(
                    sa.text("DELETE FROM app_meta WHERE key IN (:p, :s)"),
                    {"p": _META_PUBLIC, "s": _META_PRIVATE},
                )
            public, private = _generate()
            conn.execute(
                sa.text(
                    "INSERT INTO app_meta (key, value) VALUES (:pk, :pv), (:sk, :sv) "
                    "ON CONFLICT (key) DO NOTHING"
                ),
                {"pk": _META_PUBLIC, "pv": public, "sk": _META_PRIVATE, "sv": private},
            )
            rows = dict(
                conn.execute(
                    sa.text("SELECT key, value FROM app_meta WHERE key IN (:p, :s)"),
                    {"p": _META_PUBLIC, "s": _META_PRIVATE},
                ).all()
            )
            # In staging/prod this means the app-push Secret is missing —
            # subscriptions made against this key strand when it appears.
            log.warning("VAPID_* env absent — using generated keypair from app_meta")
    _cache = {"public": rows[_META_PUBLIC], "private": rows[_META_PRIVATE], "subject": subject}
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None
