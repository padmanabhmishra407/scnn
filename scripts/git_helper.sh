#!/usr/bin/env bash
# Git Helper — one-liner workflow for common operations on this repo.
# Usage: ./scripts/git_helper.sh <status|add|commit|pull|push|log|diff|stash|clean> [args]

set -euo pipefail
cd "$(dirname "$0")/.."  # cd into project root

case "${1:-status}" in
  status)   git status --short ;;
  add)      git add -A && echo "✓ staged all" ;;
  commit)   read -rp "Commit message: " msg; git commit -m "$msg";;
  pull)     git pull origin main ;;
  push)     git push origin main ;;
  log)      git log --oneline -20 ;;
  diff)     git diff --stat HEAD~1 ;;
  stash)    read -rp "Stash message: " msg; git stash push -m "$msg" ;;
  clean)    git clean -fdx && echo "✓ untracked removed" ;;
  *)        echo "Usage: $0 <status|add|commit|pull|push|log|diff|stash|clean>"; exit 1 ;;
esac
