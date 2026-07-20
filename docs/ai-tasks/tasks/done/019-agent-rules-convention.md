# 019 — Adopt the nezam agent-rules convention (paired context files)

Owner: track everything as tasks, and "start having a context file with
all relevant details as I do in nezam-devops-k3s/AGENTS.md — duplicate
this agent file here so you no longer forget."

## Result

- `AGENTS.md` gained the Agent rules section: read-on-entry list,
  `docs/ai-tasks/` as project memory, four-folder task lifecycle
  (backlog/todo/in-progress/done, `git mv` = state transition), paired
  summary + build-ready context files, update discipline (staleness audit
  every change, append-only decision logs).
- Stale AGENTS.md sections corrected in the same commit (routes → routers,
  suspended deploy gate reality + /api/version verification + dropped-push
  recovery, 131 tests + real local dev loop, release via workflow).
- Folder skeleton created; this task is the first with a paired context
  file. Tasks 001–018 remain summary-only history.
