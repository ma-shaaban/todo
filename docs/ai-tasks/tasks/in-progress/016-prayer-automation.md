# 016 — Space automations + Islamic prayer times provider

**Status:** in progress (PR B of the prayer-space project — see
`../../specs/2026-07-19-group-todos-and-automations-design.md`)

General mechanism: `spaces.automation_type/config` + a provider registry
(`app/services/automations/`) run by a second scheduler loop (15 min tick,
first run at boot and immediately on enable). Providers are idempotent via
`todos.automation_key` (unique per space).

Provider `islamic_prayers` (AlAdhan): five daily prayers as group todos
for all members, due at prayer time (local→UTC via zoneinfo), reminders
T−15 min + T (never in the past), membership sync onto future prayers,
7-day retention. Owner decisions: Cairo/Egypt/Egyptian-method default,
two reminders, keep-7-days.

API: PUT/DELETE `/api/spaces/{id}/automation` (owner-only) + automation in
the space payload. UI: 🕌 card in the Members tab.

Verification: 7 backend tests (creation, idempotency, winter-tz
conversion, member sync, retention, permissions/validation, AlAdhan-down
containment); full suite green.
