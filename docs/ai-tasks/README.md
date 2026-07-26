# The task board (`docs/ai-tasks/`)

This directory is the app's **project memory** — kept by the AI assistant,
readable by the owner. It is deliberately not part of the rendered docs
(`mkdocs.yml` nav).

- `context.md` — one-line current focus + status ledger.
- `tasks/backlog/` → `tasks/todo/` → `tasks/in-progress/` → `tasks/done/` —
  the kanban: a task's folder IS its status (`git mv` to transition).
- Each task is a **pair of files**: `<NNN>-<name>.md` (plain-language
  summary — what/why/result, written for the owner) and
  `<NNN>-context-<name>.md` (build-ready detail for the AI: paths, commands,
  snippets, traps, acceptance checks, decision log).
- `specs/` — approved feature designs. `plans/` — implementation plans.

The full convention (lifecycle, update discipline, the build-ready bar) is
in `AGENTS.md` → "Agent rules".
