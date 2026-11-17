#!/usr/bin/env bash
# End-to-end check of the plugin inside a real Duckwork; installs from git HEAD, so commit first.
set -euo pipefail

DUCKWORK=${DUCKWORK:-duckwork}
DUCKWORK_PYTHON=${DUCKWORK_PYTHON:-python3}
PLUGIN_DIR=$(cd "$(dirname "$0")/.." && pwd)
REPO_ROOT=$(git -C "$PLUGIN_DIR" rev-parse --show-toplevel)
DUCKWORK_HOME=$(mktemp -d)
# Git Bash: native Windows Python needs C:/ paths, and file:// URLs need a leading slash before the drive.
if command -v cygpath >/dev/null; then DUCKWORK_HOME=$(cygpath -m "$DUCKWORK_HOME"); fi
[[ $REPO_ROOT == /* ]] || REPO_ROOT=/$REPO_ROOT
export DUCKWORK_HOME
trap 'rm -rf "$DUCKWORK_HOME"' EXIT

step() { printf '\n== %s\n' "$*"; }

step "validate + doctor"
"$DUCKWORK" plugins validate "$PLUGIN_DIR"
"$DUCKWORK" plugins doctor "$PLUGIN_DIR" --ci

step "install from git (marketplace path)"
# No --yes-deps: tinyfish connect installs non-interactively and must still end up enabled.
# tee so a hang still shows how far the install got.
"$DUCKWORK" plugins install "file://$REPO_ROOT#duckwork" --enable </dev/null 2>&1 | tee "$DUCKWORK_HOME/install.log"
install_log=$(<"$DUCKWORK_HOME/install.log")
if grep -qi 'node dependencies' <<<"$install_log"; then
  echo "FAIL: Duckwork saw a package.json in the plugin dir" >&2
  exit 1
fi
status=$("$DUCKWORK" plugins list --json | "$DUCKWORK_PYTHON" -c \
  'import json, sys; print(next((p["status"] for p in json.load(sys.stdin) if p["name"] == "tinyfish"), "missing"))')
if [ "$status" != "enabled" ]; then
  echo "FAIL: tinyfish plugin is $status, expected enabled" >&2
  exit 1
fi

if [ -z "${TINYFISH_API_KEY:-}" ]; then
  # CI always has a key; a silent skip there once hid every live check.
  if [ -n "${CI:-}" ]; then
    echo "FAIL: TINYFISH_API_KEY unset in CI" >&2
    exit 1
  fi
  step "TINYFISH_API_KEY unset; skipping live checks"
  exit 0
fi

step "setup + live doctor"
"$DUCKWORK" tinyfish setup --yes
"$DUCKWORK" tinyfish doctor --live

step "search + extract through Duckwork' own web tools"
"$DUCKWORK_PYTHON" - <<'PY'
import asyncio
import json

from duckwork_cli.plugins import discover_plugins
from tools.web_tools import web_extract_tool, web_search_tool

discover_plugins()
search = json.loads(web_search_tool("TinyFish web agent", limit=2))
assert search["success"] and search["data"]["web"], search
extract = json.loads(asyncio.run(web_extract_tool(["https://example.com"], "markdown")))
page = extract["results"][0]
assert not page.get("error") and "Example Domain" in page["title"], page
print("search + extract OK")
PY
