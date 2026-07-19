# Design: Shared Todo Spaces with Reminders (PWA)

**Date:** 2026-07-19
**Status:** Approved by owner (autonomous build authorized, including staging merges and a production release)

## Overview

Turn the scaffolded demo app into a full todo application built around **shared spaces**: a user creates a space (e.g. "Family"), invites others via a shareable link, and members manage todos together — with due dates, assignees, recurrence, and **reminders delivered as web push notifications** to installed PWA clients on phones.

## Goals

- Email + password sign-in (Google OAuth deferred; design leaves a clean slot for it).
- Spaces with owner/member roles; invite via link/code (no email infrastructure required).
- Todos: title, notes, due date/time, priority, assignee, recurrence (daily/weekly/monthly), manual ordering, complete/reopen.
- Reminders: per-todo reminder times; delivered via Web Push + an in-app notification list.
- PWA: installable on Android/iOS home screens; push notifications on both.
- Activity feed per space; "My tasks" view across spaces.
- Backend pytest suite + frontend Vitest wired into CI (AGENTS.md explicitly requests this).
- Owner-facing TechDocs updated in plain language.

## Non-goals

- Google OAuth now (documented setup guide instead; `provider` column reserved).
- Email sending of any kind (invites are links; reminders are push/in-app).
- Multi-replica-safe scheduling beyond atomic claims (deployment is 1 replica; see Risks).
- Fork-PR preview environments (platform doesn't support them).

## Architecture fit (scaffold contract)

Everything stays inside the platform contract defined in AGENTS.md:

- One Docker image: FastAPI serves `/api/*` + built SPA via catch-all. All new routes register **above** the catch-all in `backend/app/main.py`, implemented as `APIRouter`s in separate modules and *included* from `main.py` (keeps the registration rule while keeping files focused).
- Postgres via injected `DB_*` env vars; schema changes only via Alembic migrations (auto-run at container start; all migrations idempotent-safe and additive).
- New secrets (VAPID keys) arrive as platform-injected env vars from a sops-encrypted Secret added to `nezam-devops-k3s` `k8s/tenants/ma-shaaban/todo/` — same pattern as `app-db`. Local dev falls back to auto-generated keys persisted in `app_meta`.
- Small plain-language PRs; CI-owned `newTag:` untouched; production only via the Release-to-Production workflow.

## Data model (Alembic migrations, additive)

- `users` — id (uuid pk), email (unique, stored lowercase), password_hash (nullable — future OAuth users), display_name, provider (default `'local'`), timezone (IANA string, nullable), created_at.
- `sessions` — id (uuid pk), user_id fk, token_hash (sha256 of opaque token; unique), expires_at (30 days rolling), created_at, user_agent.
- `spaces` — id, name, created_by fk, created_at.
- `space_members` — pk (space_id, user_id), role (`owner` | `member`), joined_at.
- `invites` — id, space_id fk, code (unique, URL-safe random), created_by, created_at, expires_at (7 days), revoked_at nullable.
- `todos` — id, space_id fk, title, notes (default ''), due_at (timestamptz nullable), priority (smallint 0–3, 0 = none), assignee_id (fk users, nullable), recurrence (null | `daily` | `weekly` | `monthly`), position (double for ordering), completed_at nullable, completed_by nullable, created_by, created_at, updated_at.
- `reminders` — id, todo_id fk (cascade), remind_at (timestamptz), fired_at nullable.
- `push_subscriptions` — id, user_id fk, endpoint (unique), p256dh, auth, created_at, failed_count (pruned after repeated failures).
- `notifications` — id, user_id fk, type (`reminder` | `assigned` | `completed` | `joined`), title, body, space_id nullable, todo_id nullable, read_at nullable, created_at.
- `activity` — id, space_id fk, actor_id, type, todo_id nullable, data (JSON), created_at.

All timestamps stored UTC (`timestamptz`); clients render local time and submit UTC.

## API surface (all `/api/*`, JSON, cookie session auth)

Auth: `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `PATCH /api/auth/me`.
Spaces: `GET/POST /api/spaces`, `GET/PATCH/DELETE /api/spaces/{id}` (delete/rename owner-only), `DELETE /api/spaces/{id}/members/{user_id}` (owner removes anyone; member removes self = leave).
Invites: `POST /api/spaces/{id}/invites` → `{code, url}`, `GET /api/spaces/{id}/invites`, `DELETE /api/invites/{id}` (revoke); public `GET /api/invites/{code}` (space name + inviter preview), `POST /api/invites/{code}/accept` (auth required; idempotent if already a member).
Todos: `GET /api/spaces/{id}/todos?status=open|done`, `POST /api/spaces/{id}/todos`, `PATCH /api/todos/{id}`, `DELETE /api/todos/{id}`, `POST /api/todos/{id}/complete`, `POST /api/todos/{id}/reopen`, `GET /api/me/todos` (assigned to me or created by me, across spaces). Reminder times ride inside todo create/patch payloads as `reminders: [iso8601, …]` (server diffs and replaces un-fired reminders).
Push: `GET /api/push/vapid-public-key`, `POST /api/push/subscriptions` (upsert by endpoint), `DELETE /api/push/subscriptions` (by endpoint in body).
Notifications: `GET /api/notifications?unread=1`, `POST /api/notifications/read-all`, `POST /api/notifications/{id}/read`.
Activity: `GET /api/spaces/{id}/activity` (paginated, newest first).

Authorization: every space-scoped endpoint verifies membership; owner-only actions verified server-side. 404 (not 403) for spaces the caller can't see.

## Auth design

- Passwords hashed with **argon2id** (`argon2-cffi`).
- Session: opaque 256-bit token in an `httponly`, `secure`, `samesite=lax` cookie; server stores sha256(token). Rolling 30-day expiry (re-extended on use) — important for PWA "stays signed in" UX.
- CSRF posture: SameSite=Lax + Origin/Referer check on state-changing methods + JSON-only bodies (no CORS enabled).
- Login rate limiting: in-memory sliding window per (email, IP) — adequate at 1 replica.
- Google-ready: `users.provider`, nullable `password_hash`, and an auth module boundary where an OAuth callback route slots in. A setup doc gives exact GCP steps + redirect URIs.

## Reminders & notifications

- An **asyncio poller** started in FastAPI lifespan ticks every 30s: atomically claims due reminders (`UPDATE … SET fired_at = now() WHERE fired_at IS NULL AND remind_at <= now() RETURNING`), then for each: create in-app notifications and send web push (pywebpush + VAPID) to target users' subscriptions.
- Targets: todo's assignee if set, else all space members. Assignment events push to the new assignee; completion events push to the todo's creator and assignee (excluding the actor).
- Recurring todos: completing one stamps `completed_*` and creates the next occurrence (due_at + interval, skipping into the future if overdue by more than one interval); un-fired reminders are cloned preserving their offset relative to due_at.
- Push failures: 404/410 responses delete the subscription; other failures increment `failed_count` (delete at 5).
- VAPID config: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` env vars in staging/prod (sops Secret `app-push`, wired into `deploy/base/deployment.yaml` with `optional: true` so the app still boots before the platform PR lands); local dev auto-generates a keypair once and persists it in `app_meta`.

## Frontend

- React 19 + Vite, `react-router` added. No heavy state library — a small fetch wrapper + React context for session/user, per-view hooks for data.
- Views: Login/Signup, Spaces list, Space detail (todos + members + activity tabs), Todo editor (sheet/modal), My Tasks, Notifications, Invite landing (`/invite/{code}` — preview + join, works pre-auth via redirect through login), Settings (display name, push toggle, install hint).
- Mobile-first hand-rolled CSS (CSS variables; dark mode via `prefers-color-scheme`); overdue todos highlighted; done section collapsible.
- SPA routes must survive hard refresh — already handled by the scaffold's catch-all.

## PWA

- `manifest.webmanifest` (name, theme colors, maskable + regular icons, `display: standalone`, `start_url: /`).
- Hand-rolled `sw.js` (no workbox): versioned cache, cache-first for hashed build assets, network-first→cache fallback for navigations; `push` event shows a notification; `notificationclick` focuses/opens the relevant todo's space.
- Push opt-in UI in Settings + a one-time nudge after first reminder is created. iOS requires "Add to Home Screen" before push is available — the UI detects iOS Safari and explains this; docs cover it too.

## Testing

- Backend: pytest + FastAPI TestClient against **real Postgres** (CI: service container; local: docker container). Covers auth flows, authorization boundaries (non-member 404s, owner-only rules), invite lifecycle, todo CRUD + recurrence spawn, reminder claim/fire (poller tick invoked directly), push subscription pruning.
- Frontend: Vitest for pure logic (date/recurrence formatting, api client behaviors).
- CI: a `test` job added to `ci.yaml` (pytest + vitest + `npm run build`) gating the build job. The deploy-writeback machinery is untouched.

## Delivery plan (small PRs, each merged → auto-deployed → staging-checked)

1. Test infra: pytest/httpx + Vitest wiring, CI test job with Postgres service, smoke tests of existing endpoints, this spec.
2. Auth backend + tests.
3. Spaces/members/invites backend + tests.
4. Todos/reminders backend (incl. recurrence) + tests.
5. Frontend app (auth → spaces → todos → my-tasks → invite flow).
6. Notifications: scheduler, web push, in-app list, bell UI; **platform-repo PR** adds sops VAPID Secret + deployment env wiring.
7. PWA: manifest, service worker, icons, install/push UX.
8. Activity feed + TechDocs rewrite + Google OAuth setup doc + polish.

Then: full staging user-journey verification (two accounts, real push), production release via the Release-to-Production workflow, and the scaffold evaluation report (separate deliverable to the owner, not committed here).

## Risks & trade-offs

- **Preview environments share the staging database** (platform ADR-024): a `preview`-labeled PR would run this project's migrations against staging data before merge. Mitigation: don't label migration-carrying PRs `preview`; flagged in the scaffold evaluation.
- **In-process scheduler** assumes 1 replica (the scaffold's default). Atomic claim (`RETURNING`) makes double-fire impossible even if replicas scale; late fires are possible if the pod is down (acceptable; noted in docs).
- **Push on iOS** needs home-screen install (16.4+); mitigated by in-app guidance + in-app notification list as fallback.
- **AGENTS.md says routes live in `main.py`** — satisfied via routers included from `main.py`; the tension is noted in the scaffold evaluation.

## Future work

- Google OAuth (setup doc shipped now; code slot reserved).
- Email digests/invites if the platform ever provides SMTP.
- Per-space notification preferences; snooze on reminders.
