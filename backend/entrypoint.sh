#!/bin/sh
# Container entrypoint: apply DB migrations, then start the API server.
#
# Migration failure policy (deliberate): retry `alembic upgrade head` a few
# times, then START THE SERVER ANYWAY with a loud warning. Rationale: if the
# pod crashlooped on a briefly-unreachable DB it would also take /healthz and
# the static SPA down — a transient DB blip must not turn into a full outage.
# Trade-off: code that depends on an unapplied migration may error until the
# next pod restart applies it; the WARNING below makes that state visible in
# `kubectl logs`. `alembic upgrade head` is idempotent, so re-running on every
# start is safe.
set -eu

attempts="${MIGRATE_ATTEMPTS:-3}"
delay="${MIGRATE_RETRY_SECONDS:-5}"

i=1
until alembic upgrade head; do
  if [ "$i" -ge "$attempts" ]; then
    echo "WARNING: 'alembic upgrade head' failed ${attempts}x — starting WITHOUT applying migrations (they will retry on next pod start)" >&2
    break
  fi
  echo "alembic upgrade head failed (attempt ${i}/${attempts}); retrying in ${delay}s..." >&2
  sleep "$delay"
  i=$((i + 1))
done

exec uvicorn app.main:app --host 0.0.0.0 --port 8080
