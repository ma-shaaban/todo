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
migrated=1
until alembic upgrade head; do
  if [ "$i" -ge "$attempts" ]; then
    migrated=0
    echo "WARNING: 'alembic upgrade head' failed ${attempts}x — starting WITHOUT applying migrations (a background loop keeps retrying)" >&2
    break
  fi
  echo "alembic upgrade head failed (attempt ${i}/${attempts}); retrying in ${delay}s..." >&2
  sleep "$delay"
  i=$((i + 1))
done

# Self-heal: /healthz is DB-free so kubernetes won't restart a pod that came
# up during a DB blip — without this loop the schema would stay unapplied
# (and schema-dependent endpoints would 503) until a human deleted the pod.
if [ "$migrated" -eq 0 ]; then
  (
    until alembic upgrade head; do
      echo "background migration retry failed; next attempt in 30s" >&2
      sleep 30
    done
    echo "background migration retry SUCCEEDED — schema is now up to date" >&2
  ) &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8080
