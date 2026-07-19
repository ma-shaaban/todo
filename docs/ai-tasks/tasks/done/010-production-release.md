# 010 — Production release

After 009 passes: `gh workflow run release.yaml -f bump=minor` (owner
pre-approved), verify https://todo.nezam.site serves the new version + smoke
journey on prod.

**Result:** v0.2.0 live on https://todo.nezam.site (release run 29696612964);
prod smoke passed (signup/todo/manifest/VAPID).
