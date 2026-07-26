# Developing with AI

This is the important page. Here's how to **change and grow your app** using
an AI coding assistant (like Claude Code) — even if you have never written a
line of code.

You describe what you want in plain English. The AI writes the code, following
the house rules for this app. Nothing reaches your real users until **you**
decide to release. You stay in control the whole way.

## The steps

### 1. Open this repo in an AI coding tool

Point your AI coding assistant at this app's code repository. That's all the
setup — the app already contains everything the AI needs.

### 2. Describe the change you want, in plain English

Just say what you want, the way you'd tell a colleague:

> "Add a page that shows a list of tasks, with a button to add a new one."

> "Change the heading on the home page to say 'Welcome to todo'."

> "When someone submits the form, save their name so it's remembered."

You don't need to know which part of the app to change or what the technical
terms are — the AI works that out.

### 3. The AI reads the house rules and writes the code

Before it touches anything, the AI reads **`AGENTS.md`** — the "house rules"
for your app: what it's allowed to change, how the app is laid out, and what
it must **not** break. It also keeps a running task board in
`docs/ai-tasks/` so nothing gets forgotten between sessions — you can browse
it any time to see what's planned, in progress, and done.

### 4. It opens a Pull Request — review it

Instead of changing the app directly, the AI opens a **Pull Request** (a "PR")
— a proposal that says *"here's the change I'd like to make."* Nothing is live
yet, and automatic tests run against the proposal.

You don't have to read the code. If you're unsure, just ask the AI:

> "Explain in plain English what this change does."

When you're happy, you **merge** the Pull Request to accept the change.

### 5. Staging updates by itself — the AI confirms it landed

Once your change is merged, the platform builds it and puts it on **staging**
(<https://todo-staging.nezam.site>) automatically — usually within a few
minutes. No button to press. The AI checks that the new version is actually
the one running and tells you when it's ready to look at.

> Right now there's no extra approval between "merge" and "staging" — the
> platform trusts your merge. (Staging is your preview space; your real
> users still see nothing new.) A stricter mode with a deploy-approval step
> exists and can be switched back on platform-wide later.

### 6. Happy with it? Release it to production

When the change looks good on staging and you're ready for your real users to
see it, release it. Three ways, pick any:

- Tell the AI: *"Release it to production."*
- The platform portal → your app → the **Release to Production** link.
- GitHub → **Actions** → **release** → *Run workflow* (works from a phone).

A few minutes later the new version is live on <https://todo.nezam.site>.

## The big picture

```
  describe the change  →  AI writes it (+ tests)  →  Pull Request (you accept)
        →  STAGING updates automatically (AI verifies it)
        →  you say "release"  →  live on PRODUCTION
```

## The one thing to remember

**You don't need to know how to code.** The AI follows the guardrails written
in `AGENTS.md`, tests gate every change, and **nothing reaches production
without your say-so** — you approve the change, you check it on staging, and
you decide when to release. If you're ever unsure, ask the AI to explain what
it's proposing.
