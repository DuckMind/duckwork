#!/usr/bin/env bash
# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
# Run Duckwork' own plugin checks against this checkout.
# Usage: duckwork-tools.sh <path to duckwork executable>
# The plugin is copied into a temporary DUCKWORK_HOME and enabled through config.yaml;
# `duckwork plugins enable` is not used because it needs network access.
set -euo pipefail

duckwork="$1"
root="$(cd "$(dirname "$0")/../.." && pwd)"
home="$(mktemp -d)"
dest="$home/plugins/degeneracy-guard"
mkdir -p "$dest"
cp "$root"/*.py "$root/plugin.yaml" "$dest/"
printf 'plugins:\n  enabled:\n    - degeneracy-guard\n' > "$home/config.yaml"
export DUCKWORK_HOME="$home" DEGENERACY_GUARD_HOME="$home/state"

echo "::group::duckwork plugins validate"
"$duckwork" plugins validate "$dest"
echo "::endgroup::"
echo "::group::duckwork plugins doctor degeneracy-guard --ci"
"$duckwork" plugins doctor degeneracy-guard --ci
echo "::endgroup::"
