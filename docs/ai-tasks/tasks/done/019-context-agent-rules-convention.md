# 019 context — agent-rules convention

## Background

Source convention: `../nezam-devops-k3s/AGENTS.md` ("Agent Rules" +
`.ai/tasks/` lifecycle). Adapted here with `docs/ai-tasks/` as the root
(this repo's TechDocs already claim `docs/`; ai-tasks is deliberately NOT
in `mkdocs.yml` nav so it never renders for the owner).

## What a build-ready context file must contain

Concrete file paths, code/YAML snippets, exact commands, API/schema
shapes, traps to avoid, acceptance checks, an append-only decision log.
Bar: a fresh session can execute the task from this file alone.

## Repo-specific facts future sessions need (verified 2026-07-20)

- Pipeline: PR → CI green → squash merge → CI self-merges staging deploy
  PR (ADR-028 gate suspended) → verify `/api/version == main-<sha>` on
  todo-staging.nezam.site (~3–4 min). Dropped push event → 
  `gh workflow run ci.yaml --ref main`. Prod: 
  `gh workflow run release.yaml -f bump=…`, owner go-ahead required.
- Tests: 115 pytest (needs `todo-test-pg` docker on :5433) + 16 vitest;
  venv via `uv venv --python 3.12 .venv`. Migration chain at `0008`.
  If the test DB was migrated by a NEWER branch, reset with
  `docker exec todo-test-pg psql -U todo -d todo_test -c
  "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`.
- Commit signing hangs when the user is away: repo-local
  `gpg.ssh.program` wrapper (`~/.local/bin/ssh-keygen-noagent`) already
  configured — do NOT disable signing.
- Owner preferences: light/batched reviews (pace over depth), action-first
  UX, features scoped to opt-in points (space templates, not global
  settings), plain-language PR bodies.

## Decision log

- 2026-07-20: root stays `docs/ai-tasks/` (not `.ai/`) — established
  earlier by owner request; nezam layout otherwise adopted wholesale.
- 2026-07-20: tasks 001–018 stay summary-only (history, not worth
  backfilling); paired files mandatory from 019 on.
- 2026-07-20: `status:` lines inside 012–018 summaries are legacy; the
  folder is the status going forward.
