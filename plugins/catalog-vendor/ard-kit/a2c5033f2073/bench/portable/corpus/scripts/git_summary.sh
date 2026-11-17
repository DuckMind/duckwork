#!/usr/bin/env bash
# Print a one-line summary of the current git branch and the latest commit.
set -euo pipefail
branch=$(git branch --show-current 2>/dev/null || echo "detached")
commit=$(git log -1 --oneline 2>/dev/null || echo "no commits")
echo "${branch}: ${commit}"
