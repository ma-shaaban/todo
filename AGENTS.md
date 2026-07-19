# AGENTS.md — house rules for this app

Read this first. This file tells an AI coding agent how **this specific app**
is built, what it may change freely, and — critically — how deploys work so a
change doesn't break the platform contract.

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

## Current API routes (`backend/app/main.py`)

- `GET /api/hello` — static JSON greeting.
- `GET /api/db-check` — round-trips `SELECT now()` against Postgres; returns
  503 if the DB is unreachable (never leaks raw error text to the client).
- `GET /api/version` — reports `APP_VERSION` (baked into the image at build).
- `GET /healthz` — readiness; deliberately DB-free.
- `GET /{full_path:path}` — SPA catch-all, registered **last** so every
  `/api/*` and `/healthz` route wins. Keep new API routes above it.

## How deploys work — GET THIS RIGHT

`main` is **protected**: it requires **1 approval**, and CI never
direct-pushes to it. The flow:

1. You land a change on `main` **via a Pull Request** (approved + merged).
2. CI builds the image `ghcr.io/ma-shaaban/todo:main-<shortsha>` and **opens
   a second "staging deploy" PR** that bumps the image tag in
   `deploy/staging/kustomization.yaml`.
3. A **human approves** that staging-deploy PR.
4. Auto-merge (squash, with `[skip ci]` in the commit subject so it doesn't
   loop) lands it on `main`.
5. **Flux** applies it → the change goes live at
   **`https://todo-staging.nezam.site`** (~1 minute later).

**Production** ships only by pushing a **semver git tag** (`vX.Y.Z`) — use
`./scripts/release.sh X.Y.Z`, which pins `deploy/prod/kustomization.yaml`,
commits, tags, and pushes. Flux tracks semver tags → live at
**`https://todo.nezam.site`**.

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

- `deploy/**` layout and manifests (and **never** the `newTag:` values — see
  above).
- `.github/workflows/ci.yaml` — the build / staging-deploy / release / preview
  pipeline.
- `catalog-info.yaml` annotations (`github.com/project-slug`,
  `backstage.io/techdocs-ref`, `backstage.io/kubernetes-id`) — the portal
  relies on them.
- `Dockerfile` — the single image is the deploy unit; keep it building.

## Conventions

- **FastAPI routes** go in `backend/app/main.py` (or new modules imported into
  it), and must be registered **above** the SPA catch-all at the bottom of the
  file. Keep `/api/*` prefixes for JSON endpoints.
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

**Tests:** none exist yet. When you add them, prefer `pytest` for the backend
(add `pytest` to `backend/requirements.txt`, tests under `backend/tests/`) and
Vitest for the frontend, and wire them into `.github/workflows/ci.yaml` if you
want CI to run them.

## Developing with AI (the loop, for you the agent)

The owner may not be a developer. Work like this:

1. Take their plain-English description of the change.
2. Read **this file** for the guardrails, then make the change in `backend/`,
   `frontend/`, or `docs/`.
3. Open a **Pull Request** (never push to `main` directly). Explain the change
   in plain language in the PR body so the owner can approve confidently.
4. After merge, CI opens the **staging-deploy PR** — tell the owner to
   **approve** it; the change then goes live on
   `https://todo-staging.nezam.site`.
5. When they're happy on staging, cut a release with
   `./scripts/release.sh X.Y.Z` to ship to `https://todo.nezam.site`.

Keep the owner in control: **nothing reaches production without their
approval**, and you never edit deploy image tags by hand.
