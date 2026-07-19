# template-fastapi-react

Batteries-included app template for the nezam platform: React (Vite) frontend
+ FastAPI backend, shipped as **one image**, deployed by Flux to
`https://<app>-staging.nezam.site` and `https://<app>.nezam.site`.

## Start here

1. Click **"Use this template"** on GitHub (or plain clone-and-copy — nothing
   here is GitHub-specific except the CI workflow).
2. From your new repo's root:

   ```sh
   ./scripts/init.sh <your-github-user> <app-name>   # lowercase alnum/dash
   git push
   ```

3. Ask the platform to register the app (namespaces, Flux sync, DB role — see
   the platform runbook *"Register a tenant app"*).
4. After CI's first push, make the `ghcr.io/<user>/<app>` package **public**
   (GitHub → your profile → Packages → package settings → Change visibility).
   One-time step.

## How your app ships

### Staging: merge to main (~1 minute)

Every push to `main`:

1. CI builds the image and pushes `ghcr.io/<user>/<app>:main-<shortsha>`.
2. CI commits that tag into `deploy/staging/kustomization.yaml`
   (`[skip ci] deploy: staging → main-<shortsha>`).
3. Flux (watching `main`) applies it — staging serves your build about a
   minute after CI finishes.

Every staging deploy is a git commit: the history of
`deploy/staging/kustomization.yaml` **is** your deploy log, and rollback is
`git revert`.

### Prod: cut a release

```sh
./scripts/release.sh 1.2.3
```

This pins `deploy/prod` to `1.2.3`, commits, tags `v1.2.3`, and pushes. Flux
tracks semver tags (highest wins), so the tag push is the prod deploy;
rollback = tag a higher version from an older commit.

> **Expected blip:** Flux may apply the tagged commit ~1 minute before CI
> finishes pushing the image. Prod briefly shows `ImagePullBackOff`, then
> self-heals — no action needed.

## Database

The platform provides a Postgres database per environment and injects
credentials via the `app-db` Secret, surfaced to your code as env vars:
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

Migrations are alembic, run automatically on every container start
(`alembic upgrade head` in `backend/entrypoint.sh` — idempotent; retries,
then starts the server anyway with a loud log warning so a brief DB outage
never turns into a crashloop). Add schema:

```sh
cd backend && alembic revision -m "add my_table"
```

## Preview environments

Label a same-repo PR `preview` to spin up an ephemeral environment at
`https://<app>-pr-<n>.nezam.site` within ~10 minutes (Flux default poll).

**How it works:**

1. Labeling the PR triggers CI to build `ghcr.io/<user>/<app>:pr-<n>-<sha>`.
2. The platform's Flux ResourceSetInputProvider detects the label and stamps
   a namespace + Kustomization pointing at `deploy/preview` with Flux
   `postBuild.substitute` vars `PR_ID=<n>` and `PR_SHA_SHORT=<sha>`.
3. Every push to the PR branch (with the label active) rebuilds the image and
   Flux rolls it forward automatically.
4. Removing the label, merging, or closing the PR triggers Flux staged GC —
   the namespace and all resources are removed cleanly.
5. A stale-reaper CronJob removes the `preview` label from PRs with no new
   commits in 72 hours; the env is garbage-collected within one poll cycle.

**Constraints:**

- Maximum **2 concurrent** preview environments per app (platform cap).
- **Fork PRs are not supported.** GitHub grants fork-PR workflows a read-only
  `GITHUB_TOKEN`; pushing the preview image to GHCR requires write access.
  Only same-repo branch PRs (teammates with write access to the repo) can use
  previews.
- The preview overlay deploys 1 replica with no autoscaling. It uses the same
  DB secret injection as staging — the platform stamps an isolated per-PR
  Postgres database (CNPG `Database` CR) so preview data is never commingled
  with staging or prod.

## What's where

| Path | What |
|---|---|
| `frontend/` | Vite + React SPA (one demo page hitting the API) |
| `backend/` | FastAPI: `/api/hello`, `/api/db-check`, `/api/version`, `/healthz`; serves the built SPA at `/` |
| `deploy/` | kustomize base + staging/prod/preview overlays (Deployment, Service, HTTPRoute) |
| `Dockerfile` | multi-stage: node build → python:3.12-slim runtime |
| `.github/workflows/ci.yaml` | build+push image; staging writeback on main; release build on `v*` tags; preview build on labeled PRs |
| `scripts/release.sh` | cut a prod release |
| `scripts/init.sh` | one-time placeholder substitution |
| `catalog-info.yaml` | Backstage/portal catalog stub |

The app version shown at `/api/version` is baked into the image at build time
(`--build-arg VERSION=...` → `APP_VERSION`); local builds report `dev`.

## Local development

```sh
# backend (terminal 1) — /api/db-check 503s without a local postgres; fine
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8080

# frontend (terminal 2) — dev server proxies /api → :8080
cd frontend && npm install && npm run dev
```

Or the real thing: `docker build -t myapp . && docker run -p 8080:8080 myapp`.

## Template versioning (for template maintainers)

Scaffolded apps record their origin in `catalog-info.yaml`
(`nezam.space/template-version`), and an AI upgrade skill (see `AGENTS.md`)
walks diverged apps up the version ladder. That only works with release
discipline:

- `VERSION` at the repo root holds the current release tag (e.g. `v1.1.0`)
  and MUST equal the latest `vX.Y.Z` git tag on `main`.
- Every content change ships as a PR that ALSO bumps `VERSION`; tag the
  squash-merge commit with that exact version IMMEDIATELY after merging.
- Semver intent: patch = fixes, minor = additive, major = breaks the platform
  contract / needs app-side rework.
- CI's own `deploy: staging → …` writeback commits never bump `VERSION`; the
  upgrade skill ignores that churn.
- Full maintainer procedure (edit via `gh api` without cloning, merge, tag):
  platform repo runbook, "Evolve the app template".

Apps stay fully self-contained (no shared workflows / remote bases) on
purpose — platform ADR-026: the repo must run standalone anywhere.
