#!/bin/sh
# release.sh X.Y.Z — cut a prod release (provider-neutral, plain sh + git).
# Pins deploy/prod to X.Y.Z, commits, tags vX.Y.Z, pushes both. Flux tracks
# semver tags, so pushing the tag IS the prod deploy; CI builds the matching
# ghcr image from the same tag push.
# WHEN: from the repo root, on an up-to-date main, after staging looks good.
set -eu

[ $# -eq 1 ] || { echo "usage: $0 X.Y.Z"; exit 1; }
VERSION="$1"
echo "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "'$VERSION' is not semver X.Y.Z"; exit 1; }
[ -f deploy/prod/kustomization.yaml ] || { echo "run from the repo root"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean — commit or stash first"; exit 1; }
if git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null; then
  echo "tag v$VERSION already exists"; exit 1
fi

# sed -i is not portable (BSD/macOS sed wants `-i ''`, GNU wants `-i`), so
# write to a temp file and move it into place instead.
tmp="$(mktemp)"
sed "s/newTag: .*/newTag: $VERSION/" deploy/prod/kustomization.yaml >"$tmp"
mv "$tmp" deploy/prod/kustomization.yaml
git add deploy/prod/kustomization.yaml
git commit -m "release: v$VERSION"
# Annotated (-m): plays nice with tag-signing git configs and release tooling.
git tag -m "release v$VERSION" "v$VERSION"
git push origin HEAD "refs/tags/v$VERSION"

cat <<EOF
Released v$VERSION.
Flux may apply the tagged commit ~1 minute before CI finishes pushing the
image — a brief ImagePullBackOff in prod is expected and self-heals.
EOF
