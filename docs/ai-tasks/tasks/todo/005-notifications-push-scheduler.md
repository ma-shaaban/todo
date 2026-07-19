# 005 — Notifications: web push + in-app + reminder scheduler

Platform-repo PR first: sops-encrypted `app-push` Secret (VAPID keys) under
`k8s/tenants/ma-shaaban/todo/` (owner pre-approved). Then app PR: pywebpush,
VAPID env/bootstrap, `push_subscriptions` + `notifications` tables, asyncio
poller (30s tick, atomic claim) firing reminders to assignee-or-all-members,
assignment/completion/joined events, notification list + read APIs, deployment
env wiring (`optional: true`).
