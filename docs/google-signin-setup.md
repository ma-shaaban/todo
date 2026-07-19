# Adding "Sign in with Google" later

The app currently uses email + password. The account system was built so
Google sign-in can be added without migrations or data changes — but Google
requires credentials that **only you** (the owner) can create.

## What to do in Google Cloud Console

1. Go to <https://console.cloud.google.com/> → create (or pick) a project.
2. **APIs & Services → OAuth consent screen**: choose *External*, fill in
   the app name ("Todo"), your support email, and add your domains
   (`nezam.site`). Publish it.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized JavaScript origins:
     - `https://todo-staging.nezam.site`
     - `https://todo.nezam.site`
   - Authorized redirect URIs:
     - `https://todo-staging.nezam.site/api/auth/google/callback`
     - `https://todo.nezam.site/api/auth/google/callback`
4. Copy the **Client ID** and **Client secret**.

## Handing the keys to the app

The platform injects secrets as environment variables (the same way the
database and push keys arrive). Add a sops-encrypted Secret named `app-google`
with `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in
`k8s/tenants/ma-shaaban/todo/` of the platform repo — mirroring the existing
`secrets-push.sops.yaml` — and wire the two env vars into
`deploy/base/deployment.yaml` (`optional: true`).

## Then ask your AI to finish the job

Tell it something like: *"Add Google sign-in. The GOOGLE_CLIENT_ID /
GOOGLE_CLIENT_SECRET env vars are provisioned; implement the OAuth flow at
/api/auth/google/callback, link accounts by verified email, and show a
'Continue with Google' button on the sign-in screen."*

The `users` table already has a `provider` column and passwords are optional,
so no schema change is needed.
