#!/bin/sh
# Pull the shared parts (themes, pipeline code, docs, lock file) from the public template into
# this repository, which was made from it. Your own talks, courses, blocks and assets are not
# touched. Review the diff, then commit.
#
#   scripts/update_from_template.sh            # from the template's main branch
#   scripts/update_from_template.sh v2026.10   # a tag or commit of the template
set -eu
TEMPLATE_URL="${TEMPLATE_URL:-https://github.com/jonas-ka/talks-repo-template.git}"
REF="${1:-main}"
cd "$(dirname "$0")/.."

if ! git remote get-url template >/dev/null 2>&1; then
  git remote add template "$TEMPLATE_URL"
fi
git fetch -q template "$REF"
# Shared paths. CLAUDE.md, README.md, course.yaml and your documents stay yours.
git checkout FETCH_HEAD -- themes src/talks_repo pyproject.toml uv.lock docs/STYLE.md docs/COURSES.md docs/FIGURES_README.md docs/LOGBOOK_GUIDE.md docs/labnotes-template.typ scripts/update_from_template.sh
git rev-parse --short FETCH_HEAD > .talks-template-version
uv sync -q
echo "updated from talks-repo-template $(cat .talks-template-version); review with: git status && git diff --cached"
