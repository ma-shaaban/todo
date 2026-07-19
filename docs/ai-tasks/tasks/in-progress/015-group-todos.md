# 015 — Group todos: per-person completion (completion_mode='each')

**Status:** in progress (PR A of the prayer-space project — see
`../../specs/2026-07-19-group-todos-and-automations-design.md`)

A todo can now require a check from **each** of its assignees
(`todo_assignees` rows); it completes when the last box is checked.
Reminders nag only the unchecked; My Tasks shows my pending checks; member
removal cleans up pending rows (with roll-up); recurrence clones the set
unchecked. UI: "Assign to → Everyone — each checks off", my-box circle +
n/m progress chip, per-person state in the editor.

Verification: 9 new backend tests (lifecycle, idempotency, permissions,
uncheck/reopen, validation, my-tasks, removal roll-up, recurrence,
reminder targeting); full suite 100 backend + 16 frontend green.
