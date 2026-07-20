# AGENTS.md — house rules for this app

Read this first. This file tells an AI coding agent how **this specific app**
is built, what it may change freely, and — critically — how deploys work so a
change doesn't break the platform contract.

## Agent rules — read on entry

Every session starts by reading:

1. This file (`AGENTS.md`)
2. `docs/ai-tasks/context.md` — current focus / cross-task state
3. For any task you're about to work on, resume, or whose system you're
   about to touch: its files under `docs/ai-tasks/tasks/` — **the context
   file (`<NNN>-context-<name>.md`) first** when it exists.

### `docs/ai-tasks/` is the project's memory

The authoritative source of context — ahead of training data, assumptions,
and anything you think you remember. Layout:

- `specs/` — approved designs (what/why per feature)
- `plans/` — implementation plans
- `tasks/{backlog,todo,in-progress,done}/` — one task = **paired files**:
  - `<NNN>-<kebab-name>.md` — summary: what / why / result
  - `<NNN>-context-<kebab-name>.md` — **build-ready context**: concrete
    file paths, code snippets, exact commands, API/schema shapes, traps to
    avoid, acceptance checks, and an append-only decision log. Test: could
    a fresh session build the task from this file alone? If not, it's
    incomplete.
- `context.md` — focus ledger (`focus:` + `lastVerified:` frontmatter),
  updated at every milestone

Tasks 001–018 predate the paired convention (summary-only history); every
task from 019 on carries a context file from the `todo/` transition onward.

Before acting: working on or resuming a task → read its context file
first. Touching an existing system → read the `done/` task that built it
instead of reverse-engineering. Making a decision that overlaps prior work
→ check the decision log so you don't relitigate a settled call. Context
that's missing is a gap to **fill** in the files, not to guess around.

### Task lifecycle

Status is the folder — `git mv` is the only state transition (never a
`status:` frontmatter field):

1. **backlog/** — captured ideas; summary file only is fine
2. **todo/** — committed to; summary + build-ready context both exist
   (context is written on this transition)
3. **in-progress/** — actively worked; keep the plan + decision log current
4. **done/** — fill the summary's Result section, `git mv` both files

Blocked → stays in `in-progress/` with the blocker noted in the context
file. Demoting is fine; keep the context file.

### Update discipline (load-bearing)

- **After every change, audit for staleness — proactively.** The doc set:
  this file, `README.md`, `docs/`, `docs/ai-tasks/`. If your change makes
  any of them inaccurate, fix them in the same commit. Stale docs are
  worse than missing docs.
- Non-obvious decisions go in the task's decision log — append-only;
  supersede, never edit past entries.
- Update `lastVerified:` when re-confirming a context file against
  current reality.
- Style for these files: terse, headers and lists, no emoji unless asked.

## What this is

A **FastAPI + React** app scaffolded on the **Nezam platform**. The React
frontend and FastAPI backend are built into **one Docker image**: FastAPI
serves the JSON API under `/api/*` and also serves the built React SPA at `/`.
The platform deploys that image to staging and production for you.

## Layout (the real repo)

```
backend/                 FastAPI app
  app/main.py            all API routes + SPA fallback (see routes below)
  app/__init__.py
  requirements.txt       pinned Python deps
  entrypoint.sh          runs `alembic upgrade head`, then starts uvicorn
  alembic.ini
  alembic/
    env.py
    versions/            DB migrations (one example: 0001_create_app_meta.py)
frontend/                React + Vite SPA
  src/App.jsx            the demo page (hits /api/hello, /api/db-check, /api/version)
  src/main.jsx           React entry point
  index.html
  vite.config.js         dev server proxies /api + /healthz → :8080
  package.json           react 19, vite 8
Dockerfile               multi-stage: node build → python:3.12-slim runtime
deploy/                  GitOps manifests — PLATFORM-MANAGED (see below)
  base/                  Deployment, Service, HTTPRoute, kustomization
  staging/               staging overlay — image tag written by CI
  prod/                  prod overlay — image tag pinned by scripts/release.sh
  preview/               ephemeral per-PR overlay (Flux-substituted vars)
.github/workflows/ci.yaml  CI: build image, staging deploy PR, release, preview
catalog-info.yaml        Backstage/portal catalog entry
mkdocs.yml + docs/       TechDocs (Backstage Docs tab) — plain-language owner docs
scripts/
  init.sh               one-time ma-shaaban/todo placeholder substitution
  release.sh            cut a prod release (X.Y.Z)
```

## Current API surface

Feature routers live in `backend/app/routers/` (auth, spaces, todos, push,
notifications, activity), registered in `app/main.py` **above** the SPA
catch-all. Business logic lives in `backend/app/services/` (notify,
scheduler, recurrence, vapid, `automations/` — pluggable per-space
automation providers with space-template metadata). Schema = alembic
migrations `0001`–`0008` (app_meta, auth, spaces/invites, todos/reminders,
push/notifications, activity, group todos, automations).

Template basics still present in `app/main.py`:

- `GET /api/hello`, `GET /api/db-check` (503 when DB unreachable),
  `GET /api/version` (build-baked `APP_VERSION`), `GET /healthz` (DB-free).
- `GET /{full_path:path}` — SPA catch-all, registered **last** so every
  `/api/*` and `/healthz` route wins. Keep new API routes above it.

## How deploys work — GET THIS RIGHT

Current mode (ADR-028 — deploy gate SUSPENDED; `main` is unprotected and
CI self-merges its own deploy PR):

1. Land changes on `main` **via a Pull Request** with CI green.
2. CI builds `ghcr.io/ma-shaaban/todo:main-<shortsha>`, opens a staging
   deploy PR bumping `deploy/staging/kustomization.yaml`, and **merges it
   itself immediately** (squash, `[skip ci]` subject) — no human approval
   in the loop right now.
3. **Flux** applies it → live at **`https://todo-staging.nezam.site`**
   (~3–4 min after your merge).
4. **Verify every merge yourself**: poll `/api/version` until it equals
   `main-<your short sha>`. Don't declare success before it does. If no
   `ci` push run exists for your merge sha (GitHub occasionally drops push
   events — observed live 2026-07-19), retrigger with
   `gh workflow run ci.yaml --ref main`.

**Production** ships only by a **semver git tag** (`vX.Y.Z`). Preferred:
the *Release to Production* workflow —
`gh workflow run release.yaml -f bump=patch|minor|major` (rebases, pins
`deploy/prod/kustomization.yaml`, tags, pushes). Manual fallback:
`./scripts/release.sh X.Y.Z`. Flux tracks semver tags → live at
**`https://todo.nezam.site`**. Release only with the owner's explicit
go-ahead, after they've verified staging.

> **NEVER hand-edit the `newTag:` image tags in `deploy/staging/` or
> `deploy/prod/`.** CI owns the staging tag; `scripts/release.sh` owns the
> prod tag. Editing them by hand fights the automation and breaks the deploy
> log (every deploy is supposed to be a CI/release commit).

## What you may change freely

- `backend/` — API routes, business logic, new alembic migrations.
- `frontend/` — components, pages, styling.
- Tests (add them under the conventions below — none exist yet).
- `docs/` — the TechDocs pages (keep them plain-language for the owner).

## Handle with care (the platform contract)

Change these only when the task genuinely requires it, and keep changes
minimal and reviewable:

- `deploy/**` layout and manifests — hostnames
  `<app>-staging.nezam.site` / `<app>.nezam.site`, service port **8080**,
  `/healthz` readiness — and **never** the `newTag:` values (see above).
  On the platform, the STAGING HTTPRoute is additionally rewritten at
  deploy time (KEDA scale-to-zero, platform ticket 033): its `rules` list
  is replaced wholesale to point at the interceptor — custom staging
  rules/filters in `deploy/base/httproute.yaml` will be overridden there
  (they still work when the repo is deployed standalone).
- `.github/workflows/ci.yaml` and `.github/workflows/release.yaml` — the
  build / staging-deploy / release / preview pipeline.
- `Dockerfile` — the single image is the deploy unit: it must keep serving
  HTTP on **8080** (frontend + `/api/*` + `/healthz`) and keep building.
- `catalog-info.yaml` annotations (`github.com/project-slug`,
  `backstage.io/techdocs-ref`, `backstage.io/kubernetes-id`,
  `nezam.space/template-repo`, `nezam.space/template-version`) — the portal
  and the template upgrade skill rely on them.

### Divergence warning — do this whenever a change touches the files above

These files are the PLATFORM CONTRACT: the platform builds, deploys, routes
and displays this app through them, and future template upgrades assume they
still broadly match the template. When the user asks for a change that
touches any of them:

1. **Warn in plain language**: this file is part of the platform deploy
   contract; changing it can break staging/prod deploys and will make future
   template upgrades harder (the upgrade skill has to merge around it).
2. **Offer a non-contract alternative** when one exists — most features need
   only `backend/`, `frontend/`, or `docs/`.
3. If it IS required: keep the change **minimal**, explain it in the PR body,
   and state the divergence explicitly ("diverges from template <version>:
   <what and why>").
4. **Offer an upgrade-compatibility review**: fetch the same file at the
   template's latest tag
   (`gh api "repos/nezam-org/template-fastapi-react/contents/<path>?ref=<tag>" --jq .content | base64 -d`)
   and tell the user whether their change conflicts with where the template
   is heading.

CI posts a non-blocking comment on any PR touching these paths (the
`contract-watch` job) — that net exists for direct human edits; you should
have warned before it fires.

## Template version & upgrades (the upgrade skill)

This app was scaffolded from a versioned platform template. The provenance
lives in `catalog-info.yaml`:

```yaml
metadata:
  annotations:
    nezam.space/template-repo: nezam-org/template-fastapi-react
    nezam.space/template-version: v1.1.0   # the tag this app came from
```

Template releases are git tags (`vX.Y.Z`) on the template repo. If the
annotations are missing, this app predates stamping: treat it as `v1.0.0`
and ADD both annotations in your next PR.

### How to upgrade this app to the latest template version

Run this when the user asks for an upgrade (or accepts your offer). Needs the
`gh` CLI authenticated as the repo owner.

1. **Current vs target.** Current = the `nezam.space/template-version`
   annotation (missing → `v1.0.0`). Target =
   `gh api repos/nezam-org/template-fastapi-react/tags --paginate --jq '.[].name' | sort -V | tail -1`
   (`--paginate`: the endpoint returns 30/page — unpaginated goes silently
   wrong past 30 releases).
   Equal → report "already up to date", stop. Upgrades are CUMULATIVE:
   go current → latest in ONE pass, never one release at a time.
2. **Fetch the delta.**
   `gh api "repos/nezam-org/template-fastapi-react/compare/<current>...<target>"`
   — `.files[]` carries `filename`, `status`, `patch`. If a `patch` is
   missing/truncated, read the whole file at the target:
   `gh api "repos/nezam-org/template-fastapi-react/contents/<path>?ref=<target>" --jq .content | base64 -d`.
3. **Translate template-speak.** The template's raw files use literal
   double-underscore placeholder tokens (USER, APP, TEMPLATE_VERSION wrapped
   in `__`) — this file can't spell them out, or scaffolding would substitute
   them here too. Map them before applying anything: the USER token → this
   repo's owner, the APP token → this repo's name, the TEMPLATE_VERSION
   token → the TARGET tag.
4. **Apply the delta as INTENT, file by file — never as a blind patch.**
   - File unchanged since scaffold → apply the change directly.
   - File diverged here → understand what the template change ACHIEVES and
     re-implement that intent in the current file. NEVER revert or overwrite
     user code to make a patch apply.
   - Skip entirely: the `VERSION` file (template-repo metadata — this app
     doesn't carry it) and any `newTag:` value changes in
     `deploy/*/kustomization.yaml` (deploy churn; CI owns those values here).
   - `catalog-info.yaml`: do NOT copy the template's file — set
     `nezam.space/template-version` to the target tag (add
     `nezam.space/template-repo` if missing) and merge only genuinely NEW
     annotations/links the delta introduces.
   - `AGENTS.md` (this file) is template content too — apply its changes as
     well; updated instructions take effect next session.
5. **Open a PR** — branch `template-upgrade/<target>`, never push `main`.
   Title: `chore: upgrade to template <target>`. Body: a plain-language list
   of every template change and how you handled it (applied / adapted to a
   divergence / skipped + why), so the owner can judge it without reading
   diffs.
6. **The gate: CI must be green on the PR.** Red → fix INSIDE the PR by
   adapting your application of the delta; never weaken the app's tests or CI
   to get to green; never merge red.
7. **Merge** (squash) once green. If branch protection blocks you, hand the
   merge to the owner — force nothing.
8. **Verify**: the annotation now reads `<target>`; staging deploys as usual
   after the merge.

## Conventions

- **FastAPI routes** go in `APIRouter` modules under `backend/app/routers/`,
  included from `app/main.py` **above** the SPA catch-all. Business logic
  the routes call goes in `backend/app/services/`. Keep `/api/*` prefixes
  for JSON endpoints.
- **DB schema changes** are alembic migrations:
  `cd backend && alembic revision -m "add my_table"` — a new file lands in
  `backend/alembic/versions/` next to `0001_create_app_meta.py`. Migrations
  run automatically on container start; keep them idempotent-safe.
- **React components** go in `frontend/src/`. `App.jsx` is demo scaffolding —
  replace it freely.
- **Keep the single Dockerfile building** — the frontend build stage and the
  python runtime stage must both stay green.
- **Small, reviewable PRs.** One change per PR; explain it in the PR body so
  the owner (who may not read code) can approve with confidence.

## Secrets & config

- **Never commit secrets.** No credentials, tokens, or connection strings in
  the repo.
- Database credentials and config arrive as **environment variables injected
  by the platform** from the `app-db` Secret:
  `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`. The backend reads
  them in `_db_conninfo()` in `backend/app/main.py`. `APP_VERSION` is baked
  into the image at build time.
- Need new config? Read it from an env var (with a safe local default) and ask
  the platform to inject it — don't hard-code values.

## Local dev + tests

From the repo root (commands verified against this repo's README):

```sh
# Backend (terminal 1). /api/db-check returns 503 without a local Postgres — fine.
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8080

# Frontend (terminal 2). Dev server on :5173, proxies /api → :8080.
cd frontend && npm install && npm run dev
```

Or build the real image the way the platform does:

```sh
docker build -t todo . && docker run -p 8080:8080 todo
```

**Tests:** 115 backend (pytest, `backend/tests/`, real Postgres) + 16
frontend (Vitest). CI runs both on every PR (`test` job with a Postgres
service container) and the image build gates on them. Test deps live in
`backend/requirements-dev.txt` — NOT in `requirements.txt` (they must not
ship in the runtime image). Local loop:

```sh
# One-time: local test Postgres on :5433 (conftest defaults point at it)
docker run -d --name todo-test-pg -p 5433:5432 -e POSTGRES_USER=todo \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=todo_test postgres:16-alpine

# One-time: venv (host python may lack venv — uv handles it)
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python \
  -r backend/requirements.txt -r backend/requirements-dev.txt

# Every change
cd backend && ../.venv/bin/python -m pytest -q
cd frontend && npm run test -- --run && npm run build
```

## Developing with AI (the loop, for you the agent)

The owner may not be a developer. Work like this:

1. Take their plain-English description of the change.
2. Read **this file** for the guardrails, then make the change in `backend/`,
   `frontend/`, or `docs/`.
3. Open a **Pull Request** (never push to `main` directly). Explain the change
   in plain language in the PR body so the owner can approve confidently.
4. After merge, staging deploys **automatically** (ADR-028 — gate
   suspended); verify `/api/version` == `main-<sha>` on
   `https://todo-staging.nezam.site`, then tell the owner it's ready to try.
5. When they're happy on staging and say so, release with
   `gh workflow run release.yaml -f bump=patch|minor|major` to ship to
   `https://todo.nezam.site`.

Keep the owner in control: **nothing reaches production without their
approval**, and you never edit deploy image tags by hand.
