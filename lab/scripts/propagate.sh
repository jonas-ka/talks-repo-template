#!/bin/sh
# Propagate a lab-templates tag to every consumer repository on this machine: pull the tag
# into lab/, run the repository's build check, commit and push. Uses the local git and gh
# credentials; no token needed. A consumer whose check fails is left with the pull committed
# but not pushed, and named at the end.
#
#   scripts/propagate.sh v2026.10.3            # all consumers below
#   scripts/propagate.sh v2026.10.3 karthein-cv   # one of them
#
# Consumers: path under ~/Projects and the check command run from the repository root.
set -u
TAG="${1:?usage: propagate.sh <tag> [consumer]}"
ONLY="${2:-}"
PROJECTS="${PROJECTS:-$HOME/Projects}"
consumers() {
  cat <<'EOF'
talks-repo|typst compile --root . --pdf-standard ua-1 talks/2026-09-group-meeting/main.typ /tmp/lab-check.pdf && uv run talks course build --course courses/example-course --force >/dev/null
phys206-mechanics|uv run talks course build --force >/dev/null
phys698-nucl-exp|uv run talks course build --force >/dev/null
karthein-cv|uv run cv build --public >/dev/null
cyclotron-talks|typst compile --root . --pdf-standard ua-1 docs/host-guide/host-guide.typ /tmp/lab-check.pdf
EOF
}
failed=""
consumers | while IFS='|' read -r name check; do
  [ -n "$ONLY" ] && [ "$ONLY" != "$name" ] && continue
  dir="$PROJECTS/$name"
  if [ ! -d "$dir/lab" ]; then echo "== $name: not a consumer (no lab/), skipped"; continue; fi
  echo "== $name"
  cd "$dir" || continue
  if ! git diff-index --quiet HEAD --; then echo "   uncommitted changes; skipped (commit or stash first)"; continue; fi
  if ! sh scripts/lab-templates.sh pull "$TAG" >/dev/null 2>&1; then echo "   pull failed"; continue; fi
  if (eval "$check") >/tmp/lab-check.log 2>&1; then
    git push -q && echo "   now at $(cat lab/VERSION), check passed, pushed"
  else
    echo "   check FAILED after the pull (see /tmp/lab-check.log); pull committed, not pushed"
    tail -5 /tmp/lab-check.log | sed 's/^/   | /'
  fi
done
rm -f /tmp/lab-check.pdf
