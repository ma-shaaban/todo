#!/usr/bin/env bash
# dev.sh — one-command local test loop (the same loop CI's `test` job runs).
#
#   ./scripts/dev.sh              # backend tests (Postgres in docker + venv, auto)
#   ./scripts/dev.sh --all        # + frontend tests + production build
#   ./scripts/dev.sh -k invite    # extra args are passed to pytest
#
# What it does, once: starts (or reuses) a throwaway Postgres container with
# the fixed test credentials (user todo / pass test / db todo_test — the
# contract in backend/tests/conftest.py), creates .venv (prefers uv — host
# pythons often lack the venv module), installs backend/requirements-dev.txt.
# Every run after that is just pytest.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# HOST port 5433 avoids any real local Postgres on 5432 (conftest defaults to
# 5433). Override with TEST_DB_PORT if 5433 is taken.
PG_CONTAINER="todo-test-pg"
PG_PORT="${TEST_DB_PORT:-5433}"

ALL=0
if [[ "${1:-}" == "--all" ]]; then ALL=1; shift; fi

command -v docker >/dev/null || { echo "docker is required (runs the test Postgres)"; exit 1; }

# 1. Throwaway Postgres — major matches the platform's shared cluster (18).
if ! docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
  if docker ps -a --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
    docker start "$PG_CONTAINER" >/dev/null
  else
    docker run -d --name "$PG_CONTAINER" -p "${PG_PORT}:5432" \
      -e POSTGRES_USER=todo -e POSTGRES_PASSWORD=test -e POSTGRES_DB=todo_test \
      postgres:18-alpine >/dev/null
  fi
fi
until docker exec "$PG_CONTAINER" pg_isready -q -U todo -d todo_test 2>/dev/null; do
  sleep 0.5
done

# 2. venv + deps (uv when available; plain venv/pip otherwise)
if [[ ! -d .venv ]]; then
  if command -v uv >/dev/null; then
    uv venv --python 3.12 .venv
  else
    python3 -m venv .venv
  fi
fi
if command -v uv >/dev/null; then
  uv pip install --quiet --python .venv/bin/python -r backend/requirements-dev.txt
else
  .venv/bin/pip install --quiet -r backend/requirements-dev.txt
fi

# 3. Backend tests (extra CLI args go to pytest)
(cd backend && TEST_DB_PORT="$PG_PORT" ../.venv/bin/python -m pytest -q "$@")

# 4. Frontend tests + build (--all)
if [[ "$ALL" == 1 ]]; then
  (cd frontend && npm ci && npm run test && npm run build)
fi

echo "dev.sh: all green"
