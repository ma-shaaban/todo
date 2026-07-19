"""Test fixtures: real Postgres (docker locally, service container in CI).

Env contract: TEST_DB_HOST/TEST_DB_PORT point at a throwaway Postgres
(user todo / pass test / db todo_test); defaults match
`docker run -d --name todo-test-pg -e POSTGRES_USER=todo -e POSTGRES_PASSWORD=test \
 -e POSTGRES_DB=todo_test -p 5433:5432 postgres:16-alpine`.
The DB_* vars the app reads are overwritten before the app is imported.
"""

import os
from pathlib import Path

import pytest

os.environ["DB_HOST"] = os.environ.get("TEST_DB_HOST", "localhost")
os.environ["DB_PORT"] = os.environ.get("TEST_DB_PORT", "5433")
os.environ["DB_NAME"] = "todo_test"
os.environ["DB_USER"] = "todo"
os.environ["DB_PASSWORD"] = "test"
os.environ["DISABLE_SCHEDULER"] = "1"  # the reminder poller never runs in tests

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

_TEST_ENGINE = None


def test_engine():
    global _TEST_ENGINE
    if _TEST_ENGINE is None:
        _TEST_ENGINE = sa.create_engine(
            f"postgresql+psycopg://todo:test@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/todo_test"
        )
    return _TEST_ENGINE


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def client(migrated_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_tables(migrated_db):
    yield
    with test_engine().begin() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename NOT IN ('alembic_version', 'app_meta')"
            )
        ).scalars().all()
        if rows:
            conn.execute(sa.text("TRUNCATE " + ", ".join(f'"{t}"' for t in rows) + " CASCADE"))
