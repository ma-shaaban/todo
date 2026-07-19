# 009 — End-to-end staging verification

Two-account journey on https://todo-staging.nezam.site: signup A → space →
invite link → signup B joins → shared todos (assign, complete, recurring spawn)
→ reminder fires → push received → PWA installable → dark mode → 390px layout →
SPA hard-refresh deep links. Fix-forward PRs for any defect.

**Result:** 25/26 checks passed (26th was a test-script logic error; corrected
check passed — reminder fired live: "⏰ Ping me"). Found + fixed one real
production bug: OOMKilled under concurrent argon2 hashing (PR #21).
