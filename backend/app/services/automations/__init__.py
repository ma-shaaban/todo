"""Space automations: pluggable providers the scheduler runs per space.

A provider is `run(db, space, now) -> None`, called for every space whose
`automation_type` names it — every tick, forever. Providers MUST therefore
be idempotent: todos they create carry `todos.automation_key` (unique per
space), so a re-run finds yesterday's work instead of duplicating it.
Network failures should raise; the scheduler logs and retries next tick.

Adding an automation = one module here (with a TEMPLATE metadata dict) +
one PROVIDERS entry. Users reach it as a space template on the create-space
screen (GET /api/space-templates → POST /api/spaces {template, config});
PUT /api/spaces/{id}/automation stays as the direct API.
"""

from app.services.automations import prayers

# type key → provider module. A module supplies run(db, space, now),
# validate_config(cfg) -> normalized dict (ValueError = user-facing 400),
# and TEMPLATE metadata for the create-space screen.
MODULES = {
    "islamic_prayers": prayers,
}

PROVIDERS = {key: mod.run for key, mod in MODULES.items()}

# Create-space templates, rendered generically by the frontend.
TEMPLATES = [mod.TEMPLATE for mod in MODULES.values()]
