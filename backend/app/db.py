"""Engine/session plumbing. The URL comes from the platform `app-db` Secret
env contract (DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD) — same source as
alembic/env.py. The engine is created lazily so tests can set env vars first."""

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = (
            f"postgresql+psycopg://{os.environ.get('DB_USER', 'postgres')}"
            f":{os.environ.get('DB_PASSWORD', '')}"
            f"@{os.environ.get('DB_HOST', 'localhost')}"
            f":{os.environ.get('DB_PORT', '5432')}"
            f"/{os.environ.get('DB_NAME', 'postgres')}"
        )
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5)
    return _engine


def get_db():
    """FastAPI dependency: one session per request, commit on success."""
    SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
