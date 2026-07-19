# 014 — CI never ran for two merges (GitHub dropped the push events)

**Status:** done

## Problem

Merges `6f8cfba` (live refresh) and `db3e8e5` (this fix) produced **no
`ci` push run at all** — nothing built, staging silently stayed on the
previous version. Neither commit matched `paths-ignore` or contained
`[skip ci]`; PR-event runs kept firing normally, so this was GitHub-side
push-event processing loss (run-creation lag was visible in the same
window). The merge→staging verification loop (`/api/version` must equal
`main-<sha>`) is what caught it.

## Fix

`ci.yaml` now has a `workflow_dispatch` trigger (PR #28) that behaves
exactly like a push to main — build + staging writeback — with writeback
conditions tightened to `refs/heads/main` so a dispatch on another ref can
never pin staging. Recovery is one command:

    gh workflow run ci.yaml --ref main

Used it live to un-strand `db3e8e5`: dispatched run built and deployed
`main-db3e8e5` to staging, verified.

## Lesson (fed back to the scaffold evaluation)

Always verify `/api/version` after a merge instead of trusting the green
PR check — and the template's ci.yaml should ship the dispatch escape
hatch from day one.
