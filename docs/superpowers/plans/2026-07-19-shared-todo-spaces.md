# Shared Todo Spaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the scaffolded demo into a shared-spaces todo app with reminders (web push), invite links, and PWA install — delivered as 8 small PRs through the real CI → staging pipeline, then a production release.

**Architecture:** FastAPI + SQLAlchemy 2.0 (sync ORM, psycopg3) behind the scaffold's single-image contract; routers in `backend/app/routers/*` included from `main.py` above the SPA catch-all; Alembic migrations chained off `0001`; asyncio reminder poller in FastAPI lifespan with atomic DB claims; React 19 + react-router 8 SPA; hand-rolled service worker + manifest for PWA/push. Spec: `docs/superpowers/specs/2026-07-19-shared-todo-spaces-design.md`.

**Tech Stack (pins verified against PyPI/npm 2026-07-19):** argon2-cffi==25.1.0, pywebpush==2.3.0, pytest==9.1.1, httpx==0.28.1 (backend adds); react-router@^8.2.0, vitest@^4.1.10 (frontend adds). Test DB: postgres:16-alpine (Docker locally on port 5433, service container in CI). CI Python = 3.12 (matches runtime image).

**Process rules (apply to every task):**

- Each PR task: branch from fresh `origin/main` → implement (TDD) → run full local gate (`pytest`, `vitest run`, `npm run build`, `docker build .`) → push → open PR with plain-language body (per AGENTS.md) → wait for CI checks → squash-merge → **verify staging**: poll `https://todo-staging.nezam.site/api/version` until it equals `main-<new shortsha>` (≤10 min), then smoke-test the new endpoints — before starting the next task.
- Never edit `newTag:` values. Never push `main` directly. Never commit secrets (VAPID keys only via sops in the platform repo).
- Local test Postgres (once): `docker run -d --name todo-test-pg -e POSTGRES_USER=todo -e POSTGRES_PASSWORD=test -e POSTGRES_DB=todo_test -p 5433:5432 postgres:16-alpine`.
- Commit trailer on every commit: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` + `Claude-Session: https://claude.ai/code/session_01SnteYkJtvghPA4k1u6gusP`.

---

## Task 1 — PR 1: Test infrastructure + CI test job (+ this plan/spec)

**Files:**
- Create: `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_smoke.py`
- Modify: `backend/requirements.txt` (add pytest==9.1.1, httpx==0.28.1)
- Modify: `.github/workflows/ci.yaml` (add `test` job; make `build-and-push` depend on it; run tests on `pull_request` too)
- Modify: `frontend/package.json` (add vitest devDependency + `"test": "vitest run"`)
- Create: `frontend/src/__tests__/placeholder.test.js`
- Include: the already-committed spec + this plan (branch `feat/todo-foundation`)

- [ ] **Step 1: conftest with real-Postgres fixtures.** Env-var contract: tests read `TEST_DB_HOST` (default `localhost`), `TEST_DB_PORT` (default `5433`), user `todo`/pass `test`/db `todo_test`, and export them as `DB_*` **before** importing the app. Run migrations once per session; truncate all tables between tests.

```python
# backend/tests/conftest.py
import os

import pytest

os.environ.setdefault("DB_HOST", os.environ.get("TEST_DB_HOST", "localhost"))
os.environ.setdefault("DB_PORT", os.environ.get("TEST_DB_PORT", "5433"))
os.environ.setdefault("DB_NAME", "todo_test")
os.environ.setdefault("DB_USER", "todo")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ["DISABLE_SCHEDULER"] = "1"  # poller never runs in tests (introduced in Task 5)

from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
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
    from app import db  # module added in Task 2; guard for Task 1
    import sqlalchemy as sa

    try:
        engine = db.get_engine()
    except Exception:
        return
    with engine.begin() as conn:
        rows = conn.execute(sa.text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename NOT IN ('alembic_version', 'app_meta')"
        )).scalars().all()
        if rows:
            conn.execute(sa.text("TRUNCATE " + ", ".join(f'"{t}"' for t in rows) + " CASCADE"))
```

For Task 1 only, `app.db` doesn't exist yet — wrap that import as shown (try/except ImportError also acceptable). Simplify to the final form in Task 2.

- [ ] **Step 2: smoke tests** (these pass against the current app):

```python
# backend/tests/test_smoke.py
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200

def test_hello(client):
    r = client.get("/api/hello")
    assert r.status_code == 200

def test_db_check(client):
    assert client.get("/api/db-check").status_code == 200

def test_unknown_api_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404

def test_version(client):
    assert client.get("/api/version").status_code == 200
```

- [ ] **Step 3:** `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pytest tests -v` → all smoke tests PASS (start the docker test DB first). Add `backend/.venv` to `.gitignore` if not covered.
- [ ] **Step 4: Vitest wiring.** `frontend/package.json`: devDependencies `"vitest": "^4.1.10"`, scripts `"test": "vitest run"`. Placeholder test asserting a trivial export (replaced in Task 6 by real tests). Run `npm install && npm run test` → PASS.
- [ ] **Step 5: CI.** Read `.github/workflows/ci.yaml` in full first (handle-with-care file). Add a `test` job triggered on both `pull_request` and the existing `push: main` path: postgres:16-alpine service (env as in conftest, port 5432 mapped, health-cmd `pg_isready`), `actions/setup-python@v6` python 3.12, `pip install -r backend/requirements.txt`, `TEST_DB_HOST=localhost TEST_DB_PORT=5432 pytest backend/tests -v`; then `actions/setup-node@v5` node 24, `npm ci` + `npm run test` + `npm run build` in `frontend/`. Give the existing image-build job `needs: [test]` **only for the push-to-main trigger path it already uses** — do not touch the writeback/merge steps or the preview job's trigger conditions.
- [ ] **Step 6: Commit + PR.** Plain-language PR body ("Adds automated tests and makes every future change run them before deploying. No user-visible change."). Merge after checks green; verify staging still serves `/api/hello` and `/api/version` = new `main-<shortsha>`.

## Task 2 — PR 2: Auth backend (email + password, sessions)

**Files:**
- Create: `backend/app/db.py`, `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/security.py`, `backend/app/deps.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth.py`
- Create: `backend/alembic/versions/0002_auth_tables.py` (down_revision `0001`)
- Modify: `backend/app/main.py` (include router above catch-all; add Origin-check middleware), `backend/requirements.txt` (argon2-cffi==25.1.0)
- Test: `backend/tests/test_auth.py`

**Contracts (used by all later tasks):**

```python
# backend/app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

class Base(DeclarativeBase):
    pass

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        url = (f"postgresql+psycopg://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
               f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', '5432')}/{os.environ['DB_NAME']}")
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5)
    return _engine

def get_db():
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
```

Models (`models.py`, SQLAlchemy 2.0 typed style): `User(id uuid pk default uuid4, email str unique index (store lowercase), password_hash str | None, display_name str, provider str default "local", timezone str | None, created_at datetime(timezone=True) default now)`; `Session(id uuid pk, user_id fk users.id ondelete CASCADE, token_hash str unique, expires_at tz-aware, created_at, user_agent str default "")`. Migration `0002` creates both tables + index on `sessions.user_id`.

`security.py`: `hash_password(p) / verify_password(hash, p)` via `argon2.PasswordHasher()` (catch `VerifyMismatchError` → False); `new_session_token() -> str` (`secrets.token_urlsafe(32)`); `hash_token(t)` = sha256 hexdigest; `check_login_rate(email, ip) -> bool` in-memory sliding window (10 attempts / 15 min per key, module-level dict of deques, prune on access; also expose `reset_rate_limit()` for tests); cookie helpers `set_session_cookie(response, request, token)` (httponly, samesite="lax", secure iff `request.headers.get("x-forwarded-proto") == "https"`, max_age 30 days, path "/") and `clear_session_cookie`.

`deps.py`: `get_current_user(request, db) -> User` — cookie `session` → token_hash lookup joined to user, 401 `HTTPException` if missing/expired; extends `expires_at` to now+30d when < 15d remain. Also `CurrentUser = Annotated[User, Depends(get_current_user)]`.

Origin middleware (in `main.py`): for POST/PATCH/PUT/DELETE, if `Origin` header present and its host ≠ request `Host` header host → 403. (TestClient/curl send no Origin → pass.)

**Endpoints (`routers/auth.py`, prefix `/api/auth`):**
- `POST /signup` `{email, password, display_name}` → 400 invalid email (regex `^[^@\s]+@[^@\s]+\.[^@\s]+$`) / password < 8 / display_name empty; 409 email taken (case-insensitive); else create user + session, set cookie, return `{id, email, display_name}` 201.
- `POST /login` `{email, password}` → 429 when rate-limited; 401 wrong email or password (same message both cases); else new session + cookie → user payload. Never reveal which field was wrong.
- `POST /logout` → delete current session row + clear cookie (200 even if unauthenticated).
- `GET /me` → current user `{id, email, display_name, timezone, provider}`; 401 if not signed in.
- `PATCH /me` `{display_name?, timezone?}` → validated update.

- [ ] **Step 1:** Write `backend/tests/test_auth.py` FIRST — cases: signup happy path sets cookie + `/me` works; duplicate email (different case) → 409; weak password → 400; login wrong password → 401; login unknown email → 401 (same body as wrong password); logout kills session (`/me` → 401 after); 11 rapid failed logins → 429 (call `security.reset_rate_limit()` in fixture); `PATCH /me` updates display_name; session cookie flags (httponly, samesite=lax in Set-Cookie header). Run → FAIL (modules missing).
- [ ] **Step 2:** Implement `db.py`, `models.py`, migration `0002`, `security.py`, `deps.py`, `routers/auth.py`; wire router + middleware into `main.py` **above** the SPA catch-all; simplify conftest's `clean_tables` to its final form. Run tests → PASS. Also rerun smoke tests.
- [ ] **Step 3:** Full local gate + commit + PR ("You can now create an account with email and password, and stay signed in on your devices."). Merge, staging-verify: `curl -i https://todo-staging.nezam.site/api/auth/me` → 401 JSON; signup via curl → 201 + cookie works for `/api/auth/me`.

## Task 3 — PR 3: Spaces, members, invite links

**Files:**
- Create: `backend/app/routers/spaces.py`, `backend/alembic/versions/0003_spaces_invites.py`
- Modify: `models.py`, `schemas.py`, `main.py` (include router)
- Test: `backend/tests/test_spaces.py`

Models: `Space(id, name, created_by fk, created_at)`; `SpaceMember(space_id fk ondelete CASCADE + user_id fk ondelete CASCADE composite pk, role str "owner"|"member", joined_at)`; `Invite(id, space_id fk CASCADE, code str unique default token_urlsafe(16), created_by, created_at, expires_at default now+7d, revoked_at | None)`.

`deps.py` additions: `get_membership(space_id, user, db) -> SpaceMember` raising 404 when not a member (spec: 404, never 403, for invisible spaces); `require_owner(...)`.

Endpoints (prefix `/api`): `GET /spaces` (my spaces + role + open-todo count later — count added in Task 4; return `todo_count: 0` for now and document it), `POST /spaces {name}` → space + owner membership 201; `GET /spaces/{id}` → `{id, name, my_role, members: [{id, display_name, role, joined_at}]}`; `PATCH /spaces/{id} {name}` owner-only; `DELETE /spaces/{id}` owner-only (FK cascades); `DELETE /spaces/{id}/members/{user_id}` — owner removes anyone but self; non-owner may remove only self (leave); owner cannot leave (400 "Owners can delete the space instead"); `POST /spaces/{id}/invites` (any member) → `{id, code, url: f"/invite/{code}", expires_at}`; `GET /spaces/{id}/invites` (active only); `DELETE /api/invites/{invite_id}` (member of that space) → revoke; public `GET /api/invites/{code}` → `{space_name, inviter_name, valid: bool}` (valid=false when expired/revoked — 200 either way, 404 only for unknown code); `POST /api/invites/{code}/accept` (auth) → join as member, idempotent 200 if already member, 410 if expired/revoked.

- [ ] **Step 1:** `test_spaces.py` first. Helper `make_user(client, email)` → signup + return cookies. Cases: create/list spaces; non-member GET space → 404; rename by member → 404-or-403 contract (assert 403 for member-but-not-owner — visible space, forbidden action); owner delete cascades (member's list empties); invite create → accept by second user → membership visible; accept twice → 200 idempotent; revoked invite accept → 410; expired invite (backdate `expires_at` directly via db session) → 410; owner cannot leave; member leaves; owner removes member. FAIL first.
- [ ] **Step 2:** Implement migration `0003` + models + router. Tests PASS.
- [ ] **Step 3:** Gate, PR ("Create shared spaces and invite people with a link — like a family todo list you both can edit."), merge, staging-verify with two curl-signup users end-to-end (create space → invite → accept → both see it).

## Task 4 — PR 4: Todos + reminders backend (incl. recurrence)

**Files:**
- Create: `backend/app/routers/todos.py`, `backend/app/services/__init__.py`, `backend/app/services/recurrence.py`, `backend/alembic/versions/0004_todos_reminders.py`
- Modify: `models.py`, `schemas.py`, `main.py`, `spaces.py` (real `todo_count`)
- Test: `backend/tests/test_todos.py`, `backend/tests/test_recurrence.py`

Models: `Todo(id, space_id fk CASCADE, title, notes default "", due_at tz | None, priority smallint default 0 (0..3), assignee_id fk users SET NULL | None, recurrence str | None in (daily, weekly, monthly), position float default 0, completed_at | None, completed_by | None, created_by, created_at, updated_at onupdate)`; `Reminder(id, todo_id fk CASCADE, remind_at tz, fired_at | None)`.

`services/recurrence.py` (pure functions, no DB):

```python
from datetime import datetime, timedelta, timezone
import calendar

def add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)

def next_due(due_at: datetime, recurrence: str, now: datetime) -> datetime:
    step = {"daily": lambda d: d + timedelta(days=1),
            "weekly": lambda d: d + timedelta(weeks=1),
            "monthly": lambda d: add_months(d, 1)}[recurrence]
    nxt = step(due_at)
    while nxt <= now:
        nxt = step(nxt)
    return nxt
```

Endpoints: `GET /api/spaces/{id}/todos?status=open|done|all` (default open; order: due_at nulls-last asc, priority desc, position asc, created_at asc; done ordered by completed_at desc, cap 200); `POST /api/spaces/{id}/todos` `{title, notes?, due_at?, priority?, assignee_id?, recurrence?, reminders?: [iso]}` — validate assignee is a member, reminders require due-independent absolute datetimes (allow reminders without due_at), recurrence requires due_at → 400 otherwise; `PATCH /api/todos/{id}` (member of its space; same fields; `reminders` when present replaces **un-fired** reminders only); `DELETE /api/todos/{id}`; `POST /api/todos/{id}/complete` → stamps completed_at/by; if recurrence and due_at: create next todo (same space/title/notes/priority/assignee/recurrence/created_by, due_at = `next_due(...)`, un-fired reminders cloned shifted by `new_due - old_due`), response includes `{completed: <todo>, next: <todo or null>}`; `POST /api/todos/{id}/reopen` → clears completed fields; `GET /api/me/todos` → open todos across my spaces where `assignee_id == me or (assignee_id is null and created_by == me)`, each with `space: {id, name}`; same ordering.

Todo response shape everywhere: `{id, space_id, title, notes, due_at, priority, assignee: {id, display_name} | null, recurrence, position, completed_at, completed_by, created_by, created_at, reminders: [{id, remind_at, fired_at}]}`.

- [ ] **Step 1:** `test_recurrence.py` — add_months Jan31→Feb28(/29 leap), next_due skips fully past intervals (due 10 days ago daily → tomorrow-or-today>now), weekly/monthly steps. `test_todos.py` — CRUD; non-member 404; assignee-not-member 400; complete simple; complete recurring spawns next with shifted un-fired reminders and leaves fired ones; reopen; patch replaces only un-fired reminders; my-tasks includes assigned-to-me from second space, excludes done + others' unassigned; status filter; ordering (priority desc within same due). FAIL first.
- [ ] **Step 2:** Implement `0004` + models + service + router + `todo_count` (open todos) in spaces list. PASS + full suite.
- [ ] **Step 3:** Gate, PR ("Add todos with due dates, priorities, assignment, and repeating schedules."), merge, staging-verify via curl journey.

## Task 5 — PR 5: Notifications backend + web push + scheduler + platform secret

**Order note:** the **platform PR lands first** (secret exists before the app expects it; app uses `optional: true` anyway).

**Files (platform repo, via fresh worktree of nezam-org/nezam-devops-k3s origin/main — NEVER touch the dirty main checkout):**
- Create: `k8s/tenants/ma-shaaban/todo/secrets-push.sops.yaml` (Secrets `app-push` in `ma-shaaban-todo-staging` and `ma-shaaban-todo-prod`, stringData: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT=`https://todo.nezam.site`)
- Modify: `k8s/tenants/ma-shaaban/todo/kustomization.yaml` (add resource)

- [ ] **Step 1 (platform):** Generate keys locally (throwaway venv with pywebpush): private = b64url(EC-P256 private value 32 bytes), public = b64url(X9.62 uncompressed point, 65 bytes) — verify shapes; write plaintext yaml; `sops --encrypt --in-place secrets-push.sops.yaml` (matches creation rule); confirm `sops -d` round-trips and `data|stringData` are encrypted; `git worktree add` → branch `tenant/ma-shaaban-todo-push-secret` → PR to nezam-org/nezam-devops-k3s with plain-language body → merge (ADMIN, matches platform auto-merge convention) → verify Flux applied: the portal is not needed — check via `curl`-able evidence later (staging pod picks up env in app PR); keep plaintext keys ONLY in memory/tmpfile deleted after.

**Files (app repo):**
- Create: `backend/app/services/vapid.py`, `backend/app/services/notify.py`, `backend/app/services/scheduler.py`, `backend/app/routers/push.py`, `backend/app/routers/notifications.py`, `backend/alembic/versions/0005_push_notifications.py`
- Modify: `models.py`, `main.py` (lifespan starts poller unless `DISABLE_SCHEDULER=1`), `requirements.txt` (pywebpush==2.3.0), `deploy/base/deployment.yaml` (env from secret `app-push`, each `optional: true`)
- Test: `backend/tests/test_push.py`, `backend/tests/test_scheduler.py`

Models: `PushSubscription(id, user_id fk CASCADE, endpoint text unique, p256dh, auth, created_at, failed_count int default 0)`; `Notification(id, user_id fk CASCADE, type str, title, body default "", space_id | None, todo_id | None, read_at | None, created_at)` + index (user_id, read_at).

`vapid.py`: `get_vapid() -> {public, private, subject}` — env vars if set, else generate once and persist b64url strings into `app_meta` rows (`vapid_public_key`, `vapid_private_key`) using a transaction with `INSERT ... ON CONFLICT DO NOTHING` then re-read (safe under races); subject default `https://todo.nezam.site`.

`notify.py`: `notify_users(db, user_ids, *, type, title, body, space_id=None, todo_id=None, url)` → insert Notification rows + for each active PushSubscription of those users call `send_push(sub, payload)`; `send_push` wraps `pywebpush.webpush(subscription_info, json.dumps(payload), vapid_private_key=<private>, vapid_claims={"sub": subject})` (import inside function so tests monkeypatch `notify.webpush`); on `WebPushException` with response status 404/410 → delete subscription; other failures → `failed_count += 1`, delete at ≥5; payload = `{title, body, url, tag}`.

`scheduler.py`:

```python
import asyncio, logging, os
from datetime import datetime, timezone
log = logging.getLogger("scheduler")

def tick_once() -> int:
    """Claim and fire due reminders. Returns number fired. Sync — call in a worker thread."""
    import sqlalchemy as sa
    from app.db import get_engine
    from sqlalchemy.orm import Session as OrmSession
    from app import models
    from app.services.notify import notify_users
    fired = 0
    with OrmSession(get_engine()) as db:
        claimed = db.execute(sa.text(
            "UPDATE reminders SET fired_at = now() WHERE fired_at IS NULL AND remind_at <= now() "
            "RETURNING id, todo_id")).all()
        db.commit()
        for _rid, todo_id in claimed:
            todo = db.get(models.Todo, todo_id)
            if todo is None or todo.completed_at is not None:
                continue
            if todo.assignee_id:
                targets = [todo.assignee_id]
            else:
                targets = [m.user_id for m in db.query(models.SpaceMember)
                           .filter_by(space_id=todo.space_id).all()]
            notify_users(db, targets, type="reminder", title=f"⏰ {todo.title}",
                         body="This todo is due" if todo.due_at is None else "Reminder for this todo",
                         space_id=todo.space_id, todo_id=todo.id,
                         url=f"/spaces/{todo.space_id}?todo={todo.id}")
            fired += 1
        db.commit()
    return fired

async def run_poller(stop: asyncio.Event, interval: float = 30.0):
    while not stop.is_set():
        try:
            await asyncio.to_thread(tick_once)
        except Exception:
            log.exception("reminder tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
```

`main.py` lifespan: create `stop = asyncio.Event()`, `task = asyncio.create_task(run_poller(stop))` unless `os.environ.get("DISABLE_SCHEDULER") == "1"`; on shutdown `stop.set(); await task`.

Event pushes (wire into existing routers): on todo create/patch where assignee set/changed to someone ≠ actor → notify assignee (`type="assigned"`, title `"{actor} assigned you: {title}"`); on complete → notify creator + assignee minus actor (`type="completed"`, `"✅ {actor} completed: {title}"`); on invite accept → notify existing members (`type="joined"`, `"{name} joined {space}"`).

Endpoints: `GET /api/push/vapid-public-key` → `{key}`; `POST /api/push/subscriptions` `{endpoint, keys: {p256dh, auth}}` upsert by endpoint (re-assign to current user if exists) 201; `DELETE /api/push/subscriptions` `{endpoint}` → 204 (only own); `GET /api/notifications?unread=1&limit=50` newest-first + `{unread_count}` envelope: `{items, unread_count}`; `POST /api/notifications/read-all`; `POST /api/notifications/{id}/read` (own only, 404 otherwise).

- [ ] **Step 1:** Tests first. `test_push.py`: vapid bootstrap persists + stable across calls (clear env); subscribe/list/unsubscribe; subscribe same endpoint from second user re-assigns; notifications list + unread count + read-all; assignment notification created when other member assigns (monkeypatch `notify.webpush` capture list — assert payload url/tag). `test_scheduler.py`: create todo + past-due reminder → `tick_once()` fires exactly once (second call → 0), notification rows for assignee-only when assigned / all members when not; completed todo's reminder claims but does not notify; webpush 410 (raise `WebPushException` with fake response.status_code=410 via monkeypatch) → subscription deleted; failure increments failed_count and deletes at 5. FAIL first.
- [ ] **Step 2:** Implement; deployment.yaml env block (VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY/VAPID_SUBJECT ← secretKeyRef `app-push` optional: true). PASS + full suite + docker build.
- [ ] **Step 3:** Gate, PR ("Reminders now fire and can reach your phone as notifications; in-app notification list included."), merge, staging-verify: `/api/push/vapid-public-key` returns the **platform** key (compare against generated public key → proves secret injection worked, not app_meta fallback).

## Task 6 — PR 6: Frontend app (auth, spaces, todos, my-tasks, invites)

**Files:**
- Replace: `frontend/src/App.jsx`; Modify: `frontend/src/main.jsx`, `frontend/index.html`, `frontend/package.json` (react-router ^8.2.0)
- Create: `frontend/src/api.js`, `frontend/src/auth.jsx`, `frontend/src/format.js`, `frontend/src/styles.css`, `frontend/src/components/{Layout,TodoItem,TodoEditor,Bell}.jsx`, `frontend/src/pages/{Login,Signup,Spaces,Space,MyTasks,Invite,Notifications,Settings}.jsx`
- Test: `frontend/src/__tests__/format.test.js`, `frontend/src/__tests__/api.test.js` (replace placeholder)

Core contracts:

```js
// api.js — export async function api(path, {method='GET', body}={}) → parsed JSON or throws ApiError{status, message}
// 401 → dispatch window event 'auth:required' (auth context listens, clears user)
// non-2xx → ApiError with server 'detail' when present
```

```js
// format.js — pure, unit-tested:
// dueLabel(dueAtIso, now=new Date()) → "Today 14:00" | "Tomorrow 09:00" | "Mon 22 Jul" | "Overdue — Fri 18 Jul" (isOverdue helper)
// recurrenceLabel('daily'|'weekly'|'monthly'|null) → "Repeats daily" | ... | ""
// priorityMeta(0..3) → {label: ''|'Low'|'Medium'|'High', className}
// reminderPresets(dueAtIso) → [{label:'At due time',iso}, {label:'30 min before',iso}, {label:'1 hour before',iso}, {label:'1 day before',iso}] (only future ones)
```

Routes (`react-router` v8, all imports from `"react-router"`): `/login`, `/signup`, `/invite/:code` public; authenticated shell (Layout with bottom-tab nav on mobile: Spaces / My Tasks / Notifications / Settings): `/` = Spaces list, `/spaces/:id` (tabs Todos | Members; `?todo=<id>` opens that todo's editor), `/me/todos`, `/notifications`, `/settings`. `RequireAuth` wrapper: while `GET /api/auth/me` pending show splash; 401 → redirect `/login?next=<path>`; Invite page works signed-out (preview + "Sign in to join" carrying `next=/invite/<code>`).

Behaviors: Spaces page — create space inline form, cards with name + open-count + role badge. Space page — add-todo input at top (title → quick add), todo list via `TodoItem` (checkbox toggle complete/reopen with optimistic update, title, due label with overdue class, priority chip, assignee initials, recurrence icon), tap → `TodoEditor` bottom-sheet (all fields incl. reminder presets + custom `datetime-local`, delete button), Done section collapsed by default; recurring completion shows the returned `next` todo immediately. Members tab — list, invite-link create + copy-to-clipboard (uses `{origin}/invite/{code}`), owner remove buttons, leave button. My Tasks — grouped by space, same TodoItem. Notifications — list (unread bold), tapping navigates to `url`, mark-read + read-all. Settings — display name edit, sign out; push toggle + install hint appear in Task 7. Bell in Layout header polls `GET /api/notifications?unread=1&limit=1` every 60s for `unread_count` badge.

Styling (`styles.css`): CSS variables (`--bg --card --text --muted --accent #4f7cff --danger --ok`), `prefers-color-scheme: dark` overrides, system font stack, max-width 640px centered, bottom tab bar fixed (safe-area inset), 44px touch targets, overdue = danger color, completed = strikethrough muted. No CSS framework.

- [ ] **Step 1:** Write `format.test.js` (dueLabel today/tomorrow/overdue/weekday cases with fixed `now`; reminderPresets filters past; priorityMeta) and `api.test.js` (mock global.fetch: 2xx json passthrough, 401 dispatches auth:required, error detail surfaces) → FAIL.
- [ ] **Step 2:** Implement `format.js`, `api.js` → vitest PASS.
- [ ] **Step 3:** Build the app per contracts above. `npm run build` clean; manual click-through against local backend (uvicorn + built assets or vite proxy): signup → space → invite link in second browser profile → todos with due/priority/assignee/reminders → my-tasks → notifications page.
- [ ] **Step 4:** Gate, PR ("The app now has its real interface: sign in, spaces, shared todo lists, my tasks, and notifications — designed for phones."), merge, staging-verify in real browser: full two-user journey on `todo-staging.nezam.site`.

## Task 7 — PR 7: PWA (manifest, service worker, icons, push UI)

**Files:**
- Create: `frontend/public/manifest.webmanifest`, `frontend/public/sw.js`, `frontend/public/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `frontend/src/push.js`
- Modify: `frontend/index.html` (manifest link, theme-color, apple-touch-icon, apple-mobile-web-app-capable), `frontend/src/main.jsx` (SW registration), `Settings.jsx` (push toggle + iOS install hint), `backend/app/main.py` + `backend/tests/test_smoke.py` (serve nested static paths like `/icons/x.png` safely)

Key content:

```js
// sw.js (hand-rolled, no workbox)
const CACHE = 'todo-shell-v1';
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.add('/')).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).then((r) => {
      const copy = r.clone(); caches.open(CACHE).then((c) => c.put('/', copy)); return r;
    }).catch(() => caches.match('/')));
    return;
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
      const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return r;
    })));
  }
});
self.addEventListener('push', (e) => {
  const d = e.data ? e.data.json() : {};
  e.waitUntil(self.registration.showNotification(d.title || 'Todo', {
    body: d.body || '', tag: d.tag, data: { url: d.url || '/' },
    icon: '/icons/icon-192.png', badge: '/icons/icon-192.png',
  }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const c of list) { if ('focus' in c) { c.navigate(url); return c.focus(); } }
    return self.clients.openWindow(url);
  }));
});
```

`push.js`: `isIosSafariNotInstalled()` (UA + `!window.matchMedia('(display-mode: standalone)').matches`); `enablePush()` → `Notification.requestPermission()` → `registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(await api('/api/push/vapid-public-key').key)})` → POST subscription; `disablePush()` → unsubscribe + DELETE; `urlBase64ToUint8Array` standard helper. Settings toggle reflects `pushManager.getSubscription()` state; iOS-not-installed → show "Install to Home Screen first" explainer instead of toggle.

Manifest: name "Todo", short_name, start_url "/", display "standalone", background/theme colors matching CSS, icons 192 + 512 + 512-maskable (`purpose: "maskable"`).

Icons: generate with a local Pillow script (rounded-rect accent background + white checkmark; maskable = same with 20% safe-zone padding). Script is throwaway — commit only PNGs.

Backend static serving: extend the catch-all's file branch to serve nested paths under the static dir using `Path.resolve()` + `is_relative_to` guard; add smoke tests: `/icons/icon-192.png` → 200 image/png (after build copies exist — in tests, create a temp file under the static dir or assert 404-safe behavior plus traversal rejection `/..%2f..%2fetc/passwd` → 404).

- [ ] **Step 1:** Backend static tests first (traversal + nested path) → FAIL → implement → PASS.
- [ ] **Step 2:** Manifest + icons + sw.js + registration + Settings UI. Local check: `npm run build`, serve via backend, Chrome DevTools → Application: manifest OK, SW active, installability green; push round-trip locally (DevTools push or real permission grant → create past-due reminder → notification appears).
- [ ] **Step 3:** Gate, PR ("Install the app on your phone's home screen and get reminder notifications there."), merge, staging-verify: manifest/SW load on staging, Lighthouse PWA installable pass, real push on staging (subscribe, set 1-min reminder, receive).

## Task 8 — PR 8: Activity feed + docs + polish

**Files:**
- Create: `backend/app/routers/activity.py`, `backend/alembic/versions/0006_activity.py`, `docs/google-signin-setup.md`
- Modify: `models.py`, routers (record events), `Space.jsx` (Activity tab), `docs/index.md`, `docs/how-it-works.md`, `docs/using-your-app.md`, `docs/developing-with-ai.md` (only if inaccurate), `mkdocs.yml` (nav + google doc), `README.md` (feature summary)
- Test: `backend/tests/test_activity.py`

Model: `Activity(id, space_id fk CASCADE, actor_id fk, type str, todo_id | None, data JSON default {}, created_at)` + index (space_id, created_at desc). Recorded (helper `record(db, space_id, actor, type, todo=None, **data)` called in existing endpoints): `todo_created`, `todo_completed`, `todo_reopened`, `todo_deleted` (data.title preserved), `todo_assigned` (data.assignee_name), `member_joined`, `member_left`, `member_removed`, `space_renamed`. Endpoint: `GET /api/spaces/{id}/activity?before=<iso>&limit=50` → `{items: [{id, type, actor: {id, display_name}, todo_id, data, created_at}]}`.

Activity tab renders sentence lines ("Sara completed *Buy milk*", relative time). Overdue polish: My Tasks + Space list show overdue count chip.

Docs (plain language, owner-facing): index = what the app does now; using-your-app += spaces/invites/reminders/PWA install (with iOS steps); google-signin-setup.md = exact GCP console steps, OAuth consent, authorized redirect URIs `https://todo-staging.nezam.site/api/auth/google/callback` + `https://todo.nezam.site/api/auth/google/callback`, and "hand these two values to the platform as GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET env vars via a sops secret like app-push".

- [ ] **Step 1:** `test_activity.py` — events recorded for create/complete/join/rename; non-member 404; pagination by `before`. FAIL → implement → PASS.
- [ ] **Step 2:** Frontend tab + polish; docs rewrite; `mkdocs build` locally if mkdocs available (else YAML-lint nav edit carefully).
- [ ] **Step 3:** Gate, PR ("See who did what in each space, plus refreshed help pages."), merge, staging-verify.

## Task 9 — Full staging verification (fix-forward PRs as needed)

- [ ] Two-account journey on `https://todo-staging.nezam.site` (fresh browser contexts): signup A → create space → invite → signup B via link → both manage todos → assign B → B gets in-app + (if grantable headlessly) push → recurring todo completes into next → reminder fires (1-min lead) → PWA install checks → dark mode → mobile viewport (390px) layout sane → `/api/*` unknown returns JSON 404 → SPA hard-refresh on `/spaces/<id>` works.
- [ ] Any defect → smallest fix PR through the same loop.

## Task 10 — Production release

- [ ] `gh workflow run release.yaml -R ma-shaaban/todo -f bump=minor` (Release-to-Production; owner pre-approved). Watch run → success; verify `https://todo.nezam.site/api/version` = `0.2.0` and journey smoke on prod (signup + space + todo).

## Task 11 — Scaffold evaluation report

- [ ] Write the standalone evaluation md (NOT committed to the app repo; delivered via SendUserFile): grade the scaffold on prompt→tasks conversion, guardrail accuracy (AGENTS.md staleness vs ADR-028, release.sh vs release.yaml), missing batteries (auth, tests, secret self-service, PWA), pipeline ergonomics (PR checks absent pre-Task 1, preview-shares-staging-DB hazard, deploy latency), docs quality, and concrete template diffs to adopt (each: problem → evidence from this build → suggested change).

---

## Self-review results

- **Spec coverage:** auth→T2, spaces/invites→T3, todos/recurrence/my-tasks→T4, reminders/push/in-app/VAPID/platform→T5, frontend views→T6, PWA→T7, activity/docs/Google-doc→T8, tests→every task+T1, staging verify→T9, release→T10, evaluation→T11. Gap check: spec's "manual ordering" ships as API `position` field + smart default sort, no drag UI — deliberate v1 scope, noted in PR 4 body and spec amended in that PR.
- **Type consistency:** `get_engine`/`get_db` (T2) used by scheduler (T5) ✓; todo response shape defined once (T4) and reused by T6 ✓; notification envelope `{items, unread_count}` consistent between T5 API and T6 Bell ✓; `app-push` secret name matches deployment env wiring ✓.
- **Placeholder scan:** clean — every step names exact files, commands, and behaviors; code given for all non-obvious logic (recurrence, scheduler, sw.js, conftest, db.py).
