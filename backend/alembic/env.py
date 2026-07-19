"""Alembic environment: builds the database URL from the platform `app-db`
Secret env contract (DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD)."""

import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def _database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "postgres"),
    )


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
