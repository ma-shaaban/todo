# 017 — Space templates (owner UX ruling on 016)

**Status:** done

Owner feedback on the first prayer UX: the 🕌 enable card sat in every
space's Members tab — prayer settings imposed on all spaces. Ruling:
templates belong on the create-space screen, prayers become the first
template, and the mechanism must stay pluggable.

## Shape

- Each automation module declares `TEMPLATE` metadata (key, icon, name,
  description, default space name, config fields with types/defaults/
  options). `GET /api/space-templates` serves the registry.
- `POST /api/spaces` accepts `{template, config}` — validated (including
  one real AlAdhan fetch) BEFORE the space exists, automation saved on
  the new space, immediate provider run post-commit → the space opens
  already populated.
- The Spaces screen renders template cards + a config sheet **generically
  from the metadata** — a future template ships with zero frontend
  changes.
- The Members-tab card now appears ONLY in spaces that have an
  automation (owner: edit config / turn off; members: status line).
  Blank spaces carry no prayer UI at all.
