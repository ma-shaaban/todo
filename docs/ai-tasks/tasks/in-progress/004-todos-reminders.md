# 004 — Todos + reminders backend

CRUD with membership-scoped visibility, due dates, priorities 0–3, assignees
(member-validated), daily/weekly/monthly recurrence (completion spawns the next
occurrence with offset-preserved reminders), My Tasks across spaces, open-todo
counts on the spaces list, atomic completion claim.

- **Status:** IN PROGRESS on `feat/todos` — implementation green (61 tests),
  adversarial review returned 5 confirmed majors now being fixed:
  1. recurring todos lose reminders once one fires (clone must include fired ones)
  2. reopen of a completed recurring todo orphans/duplicates the spawned successor
  3. monthly recurrence drifts to day 28 forever after crossing February
  4. NaN/Infinity `position` crashes response serialization (text/plain 500)
  5. create/spawn racing a space delete → unhandled IntegrityError
  Plus minors: drop status=all, cap open/my-tasks responses, total reminder cap.
- Then: PR, CI green, merge, staging verify.
