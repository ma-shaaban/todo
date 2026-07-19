"""Space automations: pluggable providers the scheduler runs per space.

A provider is `run(db, space, now) -> None`, called for every space whose
`automation_type` names it — every tick, forever. Providers MUST therefore
be idempotent: todos they create carry `todos.automation_key` (unique per
space), so a re-run finds yesterday's work instead of duplicating it.
Network failures should raise; the scheduler logs and retries next tick.

Adding an automation = one module here + one PROVIDERS entry. The owner
enables it per space via PUT /api/spaces/{id}/automation.
"""

from app.services.automations import prayers

PROVIDERS = {
    "islamic_prayers": prayers.run,
}
