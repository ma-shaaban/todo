# 001 — Test infra + CI gate

Add pytest (real Postgres) + Vitest wiring and a CI `test` job that gates the image
build on every PR and push.

- **Status:** DONE (PR #5, squash-merged as `2d4e4bf`; staging verified serving
  `main-2d4e4bf`).
- Backend tests run against postgres:16-alpine (docker locally on :5433, service
  container in CI); migrations applied by the session-scoped fixture; tables
  truncated between tests.
- Test-only deps in `backend/requirements-dev.txt` (kept out of the runtime image —
  deliberate deviation from AGENTS.md's "add pytest to requirements.txt", flagged
  for the scaffold evaluation).
- Smoke tests cover the template's original endpoints.
