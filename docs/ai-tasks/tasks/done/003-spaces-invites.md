# 003 — Shared spaces, members, invite links

Spaces with owner/member roles; shareable invite links (7-day expiry, revocable,
max 10 active per space); public invite preview; membership removal matrix.

- **Status:** DONE (PR #9, merged as `e22a651`; staging verified — `/api/spaces`
  401 unauthenticated).
- Adversarial review confirmed + fixed 4 majors: kicked members rejoining via
  still-active codes (kicks revoke all links; voluntary leaves don't), unbounded
  invite creation (cap + opportunistic purge), accept-invite race → text/plain 500
  (IntegrityError mapped to 200/410), `str(None)` space names (typed Pydantic
  bodies). Dead links no longer disclose space/inviter names.
- 17 new tests (44 total).
