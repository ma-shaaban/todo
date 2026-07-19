# Group todos + space automations (prayer times)

Owner brief: a "Prayer" space whose todos are auto-created from Islamic
prayer times (AlAdhan API), assigned to **everyone**, and each member checks
off their own completion. Owner ruling: build the general pieces, not a
prayer hack. Decisions given: Cairo/Egypt default (Egyptian method), push
15 min before + at prayer time, missed prayers kept 7 days then cleaned.
Deliver on staging; production release only after the owner tests.

## Feature 1 — group todos (general)

A todo has a `completion_mode`:

- `any` (default): exactly today's behavior — anyone completes it, single
  optional assignee.
- `each`: the todo carries a set of assignees (`todo_assignees` rows:
  todo_id, user_id, completed_at). Each assignee checks off **their own**
  row; the todo auto-completes when the last row is checked (atomic claim,
  same double-tap safety as today). Reopening your row reopens a fully
  completed todo (and retracts a recurrence successor, as today).

Semantics:
- Only assignees can check an `each` todo (400 otherwise).
- My Tasks shows `each` todos where **my** row is incomplete.
- Reminders on an `each` todo target only assignees who haven't checked.
- Removing/leaving a member deletes their incomplete rows; if the rest had
  all checked, the todo rolls up to completed.
- Recurrence clones the assignee set with fresh unchecked rows.
- Activity: `todo_checked` per person, `todo_completed` when it rolls up.
- completion_mode is fixed at creation (no mode switches).

UI: "Assign to → Everyone (each checks off)" in the editor; the list shows
my own check state + a `n/m` progress chip; editing shows per-person state.

## Feature 2 — space automations (general) + prayer provider

`spaces.automation_type` + `automation_config` (JSON), owner-managed via
`PUT/DELETE /api/spaces/{id}/automation`. A registry in
`app/services/automations/` maps type → provider; the scheduler runs every
provider for every configured space on its own asyncio loop (15 min tick +
immediately when enabled). Providers must be idempotent: todos they create
carry `todos.automation_key` (unique per space, e.g.
`prayer:2026-07-19:fajr`) inserted with ON CONFLICT DO NOTHING.

### Provider: `islamic_prayers`

Config `{city, country, method}` (default Cairo/Egypt/5 — Egyptian General
Authority). Each tick:
1. Today in the space's local tz (from the AlAdhan response `meta.timezone`,
   cached in config after first fetch): GET
   `https://api.aladhan.com/v1/timingsByCity/{DD-MM-YYYY}?city&country&method`
   (10 s timeout; failure = log + retry next tick).
2. For Fajr, Dhuhr, Asr, Maghrib, Isha: create a mode-`each` todo assigned
   to all current members, due at the prayer time (local→UTC via zoneinfo),
   with reminders at T−15 min and T (skipping ones already in the past),
   keyed `prayer:<date>:<name>`.
3. Sync membership onto today's future-due prayer todos (new joiners get
   rows; no one is removed here — member removal handles that).
4. Retention: delete this provider's todos with due_at older than 7 days.

## Delivery

PR A: group todos (migration 0007, API, UI, tests) → staging-verify.
PR B: automations + prayer provider (migration 0008, scheduler loop, space
settings UI, docs, tests with a mocked AlAdhan client) → staging-verify.
Hold production until the owner tests staging.
