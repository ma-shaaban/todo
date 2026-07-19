# Developing with AI

This is the important page. Here's how to **change and grow your app** using
an AI coding assistant (like Claude Code) — even if you have never written a
line of code.

You describe what you want in plain English. The AI writes the code, following
the house rules for this app. Nothing reaches your real users until **you**
approve it. You stay in control the whole way.

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

Before it touches anything, the AI reads a file called **`AGENTS.md`** in this
repo — the "house rules" for your app. That file tells it what it's allowed to
change, how the app is laid out, and what it must **not** break. Then it makes
the change for you.

### 4. It opens a Pull Request — review it

Instead of changing the app directly, the AI opens a **Pull Request** (a "PR")
— a proposal that says *"here's the change I'd like to make."* Nothing is live
yet.

You don't have to read the code. If you're unsure, just ask the AI:

> "Explain in plain English what this change does."

When you're happy, you **merge** the Pull Request to accept the change.

### 5. Approve the "deploy to staging" request

Once your change is merged, the platform automatically builds it and opens a
**second** Pull Request — a "**deploy to staging**" request. This is your
green light.

**Click approve.** Within about a minute, your change is live on
**staging** (<https://todo-staging.nezam.site>) for you to look at.

> Why the extra approval? So a change is never pushed out — even to the
> preview site — without a human saying "yes, go."

### 6. Happy with it? Release it to production

When the change looks good on staging and you're ready for your real users to
see it, **cut a release** (a "version tag"). That ships it to **production**
(<https://todo.nezam.site>). You can ask the AI to do this for you:

> "Release the current version to production."

## The big picture

```
  describe the change  →  AI writes it  →  Pull Request (you accept)
        →  approve "deploy to staging"  →  live on STAGING
        →  release a version  →  live on PRODUCTION
```

## The one thing to remember

**You don't need to know how to code.** The AI follows the guardrails written
in `AGENTS.md`, and **nothing reaches production without your approval** — you
approve the change, you approve the staging deploy, and you decide when to
release. If you're ever unsure, ask the AI to explain what it's proposing.
