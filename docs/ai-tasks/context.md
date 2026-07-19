---
focus: owner-reported fixes on top of v0.2.0 — 012 Repeat due-date hint (v0.2.1, in prod) and 013 live refresh (no more manual reload to see the other member's changes). Base: 10 PRs, 107 tests, E2E passed, scaffold evaluation delivered (2026-07-19)
lastVerified: 2026-07-19
---

# Current focus

Building the shared-todo-spaces app per `../specs/2026-07-19-shared-todo-spaces-design.md` and `../plans/2026-07-19-shared-todo-spaces.md` (paths relative to `tasks/`): 8 small PRs through the real CI → staging pipeline, then a production release and a scaffold-evaluation report for the owner.

Board: `tasks/{todo,in-progress,done}` — one file per PR-sized task, moved as status changes.

Delivery discipline (from AGENTS.md + owner rulings):
- Small plain-language PRs; merge only after CI green; verify each on
  https://todo-staging.nezam.site (`/api/version` == `main-<sha>`) before the next task.
- Owner pre-approved: autonomous merges, platform-repo sops secret PR (VAPID), and a
  production release once staging verification passes.
- Adversarial review findings get fixed before merge; keep reviews light/batched
  (owner prefers pace over exhaustive depth).

Status ledger:
- 2026-07-19: 001 merged (#5, staging-verified). 002 merged (#7, staging-verified;
  review fixed 6 majors incl. login timing oracle, XFF-spoofable rate limit,
  commit-after-response). 003 merged (#9, staging-verified; review fixed 4 majors
  incl. kicked-members-rejoin and invite-race 500s). 004 implemented (61 tests
  green); review confirmed 5 majors (recurring reminders die after first fire,
  reopen double-spawn, monthly day-drift, NaN position 500, spawn/delete race) —
  fixes in progress on feat/todos.
