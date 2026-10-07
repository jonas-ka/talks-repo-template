#!/bin/sh
# lab-templates in a consumer repository: a git subtree at lab/, pinned to a tag.
#
#   scripts/lab-templates.sh add  v2026.10.1   # once: bring the templates in (clean tree needed)
#   scripts/lab-templates.sh pull v2026.10.2   # update to a tag (read lab/CHANGELOG.md first)
#   scripts/lab-templates.sh push              # send edits made under lab/ upstream (branch lab-push/<repo>)
#   scripts/lab-templates.sh status            # the version this repository uses
#
# A subtree is a copy of another repository's files inside a folder of this one, with git
# remembering where they came from: ordinary files for Typst and Drive, and `pull`/`push`
# move changes in both directions. Only lab/ is touched; themes/logos/ and the shims are yours.
set -eu
REMOTE_URL="${LAB_TEMPLATES_URL:-https://github.com/jonas-ka/lab-templates.git}"
PREFIX="lab"
cd "$(dirname "$0")/.."
cmd="${1:-status}"; ref="${2:-main}"

ensure_remote() {
  git remote get-url lab-templates >/dev/null 2>&1 || git remote add lab-templates "$REMOTE_URL"
  git fetch -q lab-templates "$ref" 2>/dev/null || git fetch -q --tags lab-templates
}

case "$cmd" in
  add)
    ensure_remote
    git subtree add --prefix "$PREFIX" lab-templates "$ref" --squash -m "lab-templates $ref added as a subtree in $PREFIX/"
    echo "added lab-templates $ref in $PREFIX/ ($(cat $PREFIX/VERSION))" ;;
  pull)
    ensure_remote
    if ! git log -1 --grep="git-subtree-dir: $PREFIX" --format=%H | grep -q .; then
      # A repository made from talks-repo-template has lab/ as plain files without subtree
      # history: replace that copy once by the subtree, then later pulls work normally.
      echo "lab/ has no subtree history (a repository made from the template); re-adding it as a subtree"
      git rm -r -q "$PREFIX" && git commit -q -m "lab-templates: the template's copy of $PREFIX/ replaced by the subtree"
      git subtree add --prefix "$PREFIX" lab-templates "$ref" --squash -m "lab-templates $ref added as a subtree in $PREFIX/"
      echo "now at lab-templates $(cat $PREFIX/VERSION)"; exit 0
    fi
    git subtree pull --prefix "$PREFIX" lab-templates "$ref" --squash -m "lab-templates updated to $ref"
    echo "now at lab-templates $(cat $PREFIX/VERSION); review: git log -1 --stat" ;;
  push)
    ensure_remote
    repo="$(basename "$(git rev-parse --show-toplevel)")"
    git subtree push --prefix "$PREFIX" lab-templates "lab-push/$repo"
    echo "pushed $PREFIX/ to lab-templates branch lab-push/$repo; open a pull request there, then tag and pull the tag here" ;;
  status)
    echo "lab-templates $(cat $PREFIX/VERSION 2>/dev/null || echo 'not installed')" ;;
  *)
    echo "usage: $0 add|pull <tag> | push | status" >&2; exit 2 ;;
esac
