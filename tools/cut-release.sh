#!/bin/bash
# Cut a public release. `main` is the working line and keeps its whole history; what ships is the
# `public` branch, one commit per release, built from main's tree under the project's GitHub
# identity, after a scan for anything that must never leave this machine.
#
#   tools/cut-release.sh            # from main
#   tools/cut-release.sh dev        # from another branch
#   git push origin public:main --follow-tags
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
NAME="LayerMakerLab"
EMAIL="290883952+LayerMakerLab@users.noreply.github.com"
src=${1:-main}
version=$(tr -d '[:space:]' < VERSION)

[ -z "$(git status --porcelain)" ] || { echo "cut-release: commit or stash first" >&2; exit 1; }

# Nothing private ships: mail addresses, home-network and Tailscale addresses, printer serials,
# home directories, API keys. Test fixtures use made-up values and are scanned too.
leaks=$(git grep -n -I -E \
  '[A-Za-z0-9._%+-]+@(gmail|icloud|hotmail|yahoo)\.[a-z]+|10\.0\.0\.[0-9]+|100\.[0-9]+\.[0-9]+\.[0-9]+|01P00[A-Z0-9]{10}|03919[A-Z0-9]{10}|/home/[a-z]{3,}|/Users/[a-z]{3,}|msy_[A-Za-z0-9]{8}|accessCode": "[0-9]{8}"' \
  "$src" -- . ':!tools/cut-release.sh' || true)
if [ -n "$leaks" ]; then
  echo "cut-release: these lines must not ship:" >&2
  echo "$leaks" | sed "s|^$src:||" >&2
  exit 1
fi

tree=$(git rev-parse "$src^{tree}")
parent=$(git rev-parse -q --verify refs/heads/public 2>/dev/null || true)
if [ -n "$parent" ] && [ "$(git rev-parse 'public^{tree}')" = "$tree" ]; then
  echo "cut-release: public already matches $src ($(git rev-parse --short public))"
  exit 0
fi
commit=$(GIT_AUTHOR_NAME=$NAME GIT_AUTHOR_EMAIL=$EMAIL GIT_COMMITTER_NAME=$NAME GIT_COMMITTER_EMAIL=$EMAIL \
  git commit-tree "$tree" ${parent:+-p "$parent"} -m "omarchy-maker $version")
git branch -f public "$commit"
if git rev-parse -q --verify "refs/tags/v$version" >/dev/null; then
  echo "cut-release: tag v$version exists; bump VERSION or move it yourself" >&2
else
  GIT_COMMITTER_NAME=$NAME GIT_COMMITTER_EMAIL=$EMAIL git tag -a "v$version" -m "omarchy-maker $version" public
  echo "cut-release: tagged v$version"
fi
echo "cut-release: public -> $(git rev-parse --short public) (omarchy-maker $version, tree of $src)"
echo "push with: git push origin public:main --follow-tags"
