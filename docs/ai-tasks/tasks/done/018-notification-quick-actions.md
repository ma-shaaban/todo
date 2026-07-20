# 018 — Notification quick actions (owner UX report)

**Status:** done

Owner: "when I get a notification, I open it and it goes to edit the
task… I want to open it to mark it as done or something. or even mark it
as done from the notification bar."

## Fix

- **Notification bar**: push payload now carries `type` + `todo_id`; the
  service worker adds a **✓ Mark done** action to reminder/assigned
  pushes. The action handler POSTs `/api/todos/{id}/complete` straight
  from the SW (same-origin: session cookie + Origin pass the CSRF guard;
  on a group todo it checks MY box). Failure shows a "couldn't mark it
  done" notification that opens the app. Android/desktop Chrome only —
  iOS ignores web-notification actions.
- **Tap-through**: the `?todo=` deep link now opens a quick-action panel
  (title, due, notes, per-person state) with a primary **Mark done** /
  **Check off my box** button, plus Edit details / Close — instead of
  dropping into the edit form.
