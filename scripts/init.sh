#!/usr/bin/env bash
# init.sh <github-user> <app-name> — personalize a fresh copy of the template.
# Substitutes the ma-shaaban/todo placeholders in deploy/ + catalog-info.yaml
# (image ghcr.io/<user>/<app>, hostnames <app>-staging.nezam.site /
# <app>.nezam.site) and commits the result.
# WHEN: once, right after creating your repo from this template.
set -euo pipefail

[[ $# -eq 2 ]] || { echo "usage: $0 <github-user> <app-name>"; exit 1; }
[[ -f deploy/base/kustomization.yaml ]] || { echo "run from the repo root"; exit 1; }
USER_ARG="$1"; APP_ARG="$2"
[[ "$USER_ARG" =~ ^[a-z0-9-]+$ && "$APP_ARG" =~ ^[a-z0-9-]+$ ]] || { echo "lowercase alnum/dash only"; exit 1; }
grep -rq "todo" deploy catalog-info.yaml || { echo "no placeholders left — already initialized?"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "working tree not clean — commit or stash first"; exit 1; }
[[ -f VERSION ]] || { echo "VERSION file missing — incomplete template copy?"; exit 1; }
TEMPLATE_VERSION="$(cat VERSION)"   # e.g. v1.1.0; $() strips the newline

# sed -i is not portable (BSD/macOS sed wants `-i ''`, GNU wants `-i`), so
# write to a temp file and move it into place instead.
for f in deploy/base/*.yaml deploy/staging/*.yaml deploy/prod/*.yaml deploy/preview/*.yaml catalog-info.yaml; do
  tmp="$(mktemp)"
  sed -e "s/ma-shaaban/$USER_ARG/g" -e "s/todo/$APP_ARG/g" \
      -e "s/v1.1.0/$TEMPLATE_VERSION/g" "$f" >"$tmp"
  mv "$tmp" "$f"
done

# VERSION is template-repo metadata; the catalog-info annotation is the app's
# record (owner ruling, platform ticket 036).
git rm -q VERSION

git add deploy catalog-info.yaml
git commit -m "chore: initialize $APP_ARG from template"

cat <<EOF
Initialized as $USER_ARG/$APP_ARG. Next:
  1. git push
  2. Ask the platform to register the app (register-tenant.sh $USER_ARG $APP_ARG
     + the app-db Secret steps) — see the platform runbook "Register a tenant app".
  3. Make the ghcr.io/$USER_ARG/$APP_ARG package public after CI's first push
     (GitHub > Packages > package settings), or arrange the side-load fallback.
EOF
