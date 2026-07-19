# 013 — Other members' changes need a manual refresh

**Status:** done
**Reported by:** owner ("the app needs to be refreshed manually for my
updates to show on the other member's screen")

## Problem

Every page fetched its data once on mount. Member A's changes never
appeared on member B's screen until B manually reloaded — the only thing
that polled was the unread badge (60s).

## Fix

`useLiveRefresh(fn, intervalMs = 15000)` hook (`frontend/src/live.js`):
re-runs a silent refetch on an interval **only while the tab is visible**,
plus immediately on `visibilitychange`/`focus` (PWA resume). Wired into:

- **Space** — space+members, open todos, plus the done list / activity feed
  when shown; a 404 during refresh flips to not-found (space deleted).
- **My Tasks**, **Alerts**, **Spaces list** — same hook around their loads
  (background failures are silent; only user-initiated loads show errors).
- **Layout** unread badge — moved onto the hook at 30s (was 60s).

No websockets/SSE: polling at one request per open page per 15s is nothing
at this scale, works through the gateway unchanged, and pauses in
background tabs. Upgrade path if it's ever needed: SSE endpoint + in-process
pub/sub (single replica).

## Verification

- 16 frontend tests + build pass; CI green.
- Staging, two browsers: todo added in one appears in the other within 15s
  untouched; done list and activity refresh too; error banners don't flash
  when a refresh fails in the background.
