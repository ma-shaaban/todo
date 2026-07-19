# How it works

Your app is made of a few simple parts working together. You don't need to
understand the details — but a quick mental picture helps when you're asking
an AI assistant to change something.

## The parts

- **Frontend** — this is what people see and click in their web browser: the
  pages, buttons, text, and layout. (Built with a tool called *React*.)
- **Backend** — the "brains" behind the scenes. When the frontend needs to
  save something, look something up, or do a calculation, it asks the backend.
  (Built with a tool called *FastAPI*.)
- **Database** — the app's memory. Anything that needs to be remembered
  between visits — accounts, entries, settings — lives here. (A *Postgres*
  database.)

All three are packaged together and **deployed automatically** by the
platform. When you make a change, you don't build, upload, or install
anything — the platform picks up your change, wraps it up, and puts it online
for you.

## A simple picture

```
   You / your users
         |
   [ web browser ]
         |
   FRONTEND  (what you see — the pages and buttons)
         |
   BACKEND   (the brains — answers requests, runs the logic)
         |
   DATABASE  (the memory — remembers your data)

   ── all packaged together and deployed automatically ──
             by the Nezam platform
```

## What this means for you

When you ask for a change, it usually touches one of these parts:

- "Make the button blue" or "add a page" → the **frontend**.
- "Save this when someone submits the form" → the **backend** and the
  **database**.

You can describe the change in those everyday terms — an AI assistant will
figure out which part to edit. See
**[Developing with AI](developing-with-ai.md)**.
