#!/usr/bin/env bash
# Publish the already-validated data commit; never recollect or force-push.
set -euo pipefail
base=$(git rev-parse HEAD^)
candidate=$(git rev-parse HEAD)
if [[ -n $(git status --porcelain) ]]; then
  echo 'Publication stopped: working tree must be clean.' >&2
  exit 1
fi
git fetch origin main
remote=$(git rev-parse FETCH_HEAD)
if [[ "$remote" != "$base" ]]; then
  git merge-base --is-ancestor "$base" "$remote" || {
    echo 'Publication stopped: remote history diverged from collection baseline.' >&2
    exit 1
  }
  # An overlapping file is not safe even if Git could textually auto-merge it.
  overlap=$(comm -12 <(git diff --name-only "$base" "$candidate" | LC_ALL=C sort) <(git diff --name-only "$base" "$remote" | LC_ALL=C sort))
  if [[ -n "$overlap" ]]; then
    printf 'Publication stopped: concurrent changes overlap collected files:\n%s\nCandidate retained at %s\n' "$overlap" "$candidate" >&2
    exit 1
  fi
  git rebase --onto "$remote" "$base" || {
    git rebase --abort
    echo "Publication stopped: integration conflict; candidate retained at $candidate" >&2
    exit 1
  }
  # Updated code/schema and the data candidate must pass together.
  bash scripts/validate_publication.sh
  if [[ -n $(git status --porcelain) ]]; then
    echo 'Publication stopped: validation modified the candidate working tree.' >&2
    exit 1
  fi
fi
# A later race must fail closed; no force, automatic recollection or blind retry.
git push origin HEAD:main
