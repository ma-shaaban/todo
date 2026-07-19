# 012 — Repeat select looks broken without a due date

**Status:** done
**Reported by:** owner ("the repeat button is not working, it seems disabled")

## Problem

The Repeat select in the todo editor is disabled until the todo has a due
date (by design: a repeat re-creates the todo for the *next due date* on
completion, and the API rejects `recurrence` without `due_at`). Nothing in
the UI said why, so the control read as broken.

## Fix

- `TodoEditor.jsx`: show a "Set a due date to repeat" hint under the Repeat
  select (plus a tooltip) whenever no due date is set. The constraint itself
  is unchanged — it matches the backend contract.
- `docs/using-your-app.md`: repeats section now says a due date is required.

## Verification

- 16 frontend tests + build pass locally; CI green on the PR.
- Staging: editor shows the hint with no due date, Repeat enables once a
  date is picked.
