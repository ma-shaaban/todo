# Using your app

Your app has two addresses. They look almost the same, but they're for very
different things.

## Staging — the preview

**<https://todo-staging.nezam.site>**

Staging always shows the **latest** version of your app — every change lands
here first, automatically, within about a minute of being approved.

Use staging to:

- See a change working before anyone else does.
- Try things out and click around safely.
- Show work-in-progress to a teammate.

Think of staging as a rehearsal space. It's fine for things to be rough or
half-finished here — that's the whole point.

## Production — the real thing

**<https://todo.nezam.site>**

Production is the **released** version — the one your actual users see and
rely on. It only updates when you deliberately **release** a new version.
Nothing reaches production by accident.

Use production for:

- The stable app your users depend on.
- Only changes you've already checked on staging and are happy with.

## The short version

| | Staging | Production |
|---|---|---|
| Address | `todo-staging.nezam.site` | `todo.nezam.site` |
| Shows | the latest work | released versions |
| Updates | automatically (after you approve) | only when you release |
| For | previewing & testing | your real users |

**The habit:** every change appears on **staging** first. When it looks good
there, you **release** it to **production**. How that works step by step is on
the **[Developing with AI](developing-with-ai.md)** page.
