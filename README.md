# todo

**todo** is a shared to-do app — spaces you invite people into, group todos,
reminders, and web-push notifications — running on the Nezam platform. This
page is for you, the owner: you don't need to be a developer to change it and
ship it.

## Your app's two addresses

| | URL | What it's for |
|---|---|---|
| **Staging** | <https://todo-staging.nezam.site> | Every change lands here first, automatically. Look at it, click around, break things safely. |
| **Production** | <https://todo.nezam.site> | The released version your real users see. Updates only when you say "release". |

Staging and production keep **separate accounts and data** — an account made
on staging doesn't exist on production.

## How you build this app: describe, review, release

You work with an AI coding assistant (Claude Code or similar). Open this
repository in it and describe what you want, in plain English:

> "Add a weekly view that groups todos by the day they're due."

The AI reads this repo's house rules (`AGENTS.md` — what it may change, what
it must not break, how deploys work) and does the rest:

1. **It proposes the change as a Pull Request.** Nothing is live yet, and
   automatic tests run against it. You don't have to read code — ask it to
   explain the change in plain English, then accept (merge) it.
2. **Staging updates automatically.** A few minutes after the merge, the
   change is live on staging. The AI verifies the deploy actually landed and
   tells you when it's ready to try.
3. **You decide when to release.** When staging looks good, say "release
   it" — or use the **Release to Production** button (in the platform
   portal, or GitHub → Actions → release → Run workflow). Production
   updates a few minutes later.

Nothing reaches your users without your go-ahead.

## Where to look things up

- **`docs/`** — plain-language pages about your app (also rendered on the
  portal's *Docs* tab): what it is, how it works, [using your
  app](docs/using-your-app.md) (spaces, reminders, prayer-space template,
  installing it on your phone), [developing with AI](docs/developing-with-ai.md).
- **`docs/ai-tasks/`** — the AI's task board for this app: what's planned
  (`tasks/todo/`), in progress, and done (`tasks/done/`). Browse it any time
  to see where work stands — each task has a short summary written for you.
- **`AGENTS.md`** — the house rules the AI follows. You rarely need to read
  it, but everything the AI is and isn't allowed to do is written there.

## Your database, backups, and limits — handled

The platform provides a Postgres database per environment (staging and
production fully separate), injects the credentials automatically, and applies
schema changes on deploy. Your app has a resource budget suited to a small
production app; the AI knows the numbers and can raise them within your quota
if a feature needs more muscle.

## For developers

The short version (the full contract is in `AGENTS.md`):

- **Stack:** React (Vite) frontend + FastAPI backend + Postgres, shipped as
  one Docker image; FastAPI serves `/api/*` and the built SPA. Feature
  routers in `backend/app/routers/`, business logic in `backend/app/services/`.
- **Tests:** backend pytest against a real Postgres + Vitest on the frontend;
  CI runs both and gates every image build on them.
- **Local dev:** `cd backend && uvicorn app.main:app --port 8080` and
  `cd frontend && npm run dev` (the dev server proxies `/api`).
- **Deploys:** merge to `main` → CI builds + writes the image tag back →
  Flux deploys staging; semver tag (via the release workflow) → production.
  Every deploy is a git commit — the history of `deploy/` is your deploy log.
- **Previews:** label a PR `preview` for an ephemeral environment at
  `https://todo-pr-<n>.nezam.site` (careful: previews share the staging
  database — see `AGENTS.md`).
