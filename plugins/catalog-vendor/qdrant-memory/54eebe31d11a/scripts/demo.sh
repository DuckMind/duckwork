#!/bin/bash
# Demo: durable memory with the qdrant-memory plugin, in embedded mode.
#
# The script uses a dedicated DUCKWORK_HOME, so it does not touch an existing
# Duckwork profile. It installs the pinned release, teaches a preference,
# waits for the background extraction, recalls the preference in a new
# session, and walks through export and scoped deletion.
#
# The final step deletes the whole demo scope, so the script refuses to run
# when that scope already holds memories. Use a fresh demo home.
#
# The script marks the demo home it creates (a `.qdrant-demo-home` file) and
# refuses to modify an existing Duckwork home that lacks the marker, because
# the setup steps change the home (plugin install, memory.provider).
#
# Requirements:
#   - The Duckwork CLI (`duckwork`) on PATH.
#   - `python3` on PATH (the script reads the CLI's JSON output).
#   - `git` on PATH (the plugin installer clones the repository).
#   - Ollama running locally, with the embedding model pulled:
#       ollama pull qwen3-embedding:4b
#   - A model configuration in the demo home. When the demo home has none,
#     start one Duckwork session in it and complete the model setup, for
#     example with the default demo home:
#       DUCKWORK_HOME=~/.duckwork-qdrant-demo duckwork
#
# Usage: bash scripts/demo.sh [DEMO_HOME]
#   Default DEMO_HOME: $HOME/.duckwork-qdrant-demo
#
# The script drives Duckwork non-interactively:
#   duckwork plugins install <url> --ref <sha> [--yes-deps]
#       --yes-deps consents to dependency preparation at install time and is
#       passed only when the CLI supports it. Interactive shells can answer
#       the prompt instead; the minimum supported Duckwork prepares
#       dependencies by default.
#   duckwork chat -q "<query>" --reasoning none
#       One-shot session with compact output; the reasoning panel stays
#       hidden so the demo transcript stays short.

set -euo pipefail
DEMO_HOME="${1:-$HOME/.duckwork-qdrant-demo}"
RELEASE_REF="5babd3e4b4c022aad38a2b6db82cbd5b601f1ef8"   # v0.1.0 release commit
export DUCKWORK_HOME="$DEMO_HOME"
say() { printf '\n\033[1;36m▸ %s\033[0m\n' "$1"; }
fail() { echo "demo step failed: $*" >&2; exit 1; }

command -v duckwork >/dev/null || { echo "duckwork CLI not found on PATH" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 not found on PATH" >&2; exit 1; }
MARKER="$DEMO_HOME/.qdrant-demo-home"
if [ -e "$DEMO_HOME" ] && [ -n "$(ls -A "$DEMO_HOME" 2>/dev/null)" ] && [ ! -e "$MARKER" ]; then
  echo "Refusing to modify an existing directory: $DEMO_HOME" >&2
  echo "The demo changes the home it runs in (plugin install, memory.provider)." >&2
  echo "Use a fresh path, or mark this home as a demo home first:" >&2
  echo "  touch \"$MARKER\"" >&2
  exit 1
fi
mkdir -p "$DEMO_HOME"
touch "$MARKER"
if ! grep -q '^model:' "$DEMO_HOME/config.yaml" 2>/dev/null; then
  echo "No model configuration in $DEMO_HOME/config.yaml." >&2
  echo "Start one Duckwork session in the demo home and complete the model" >&2
  echo "setup, then run this script again:" >&2
  echo "  DUCKWORK_HOME=$DEMO_HOME duckwork" >&2
  exit 1
fi

# Chat steps get a hard timeout (independent of the extraction wait below):
# a timeout command when available (GNU timeout or gtimeout), a bounded wait
# with a process-group kill otherwise.
run_chat() {
  local seconds="$1" query="$2" timeout_cmd=""
  if command -v timeout >/dev/null 2>&1; then timeout_cmd="timeout"
  elif command -v gtimeout >/dev/null 2>&1; then timeout_cmd="gtimeout"; fi
  if [ -n "$timeout_cmd" ]; then
    "$timeout_cmd" "$seconds" duckwork chat -q "$query" --reasoning none </dev/null
    return $?
  fi
  set -m
  duckwork chat -q "$query" --reasoning none </dev/null &
  local pid=$!
  set +m
  local waited=0
  while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt "$seconds" ]; do
    sleep 2; waited=$((waited + 2))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    echo "chat timed out after ${seconds}s" >&2
    return 124
  fi
  wait "$pid"
}

memories_total() {
  duckwork qdrant-memory list --user duckwork-user --agent duckwork 2>/dev/null \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['count']['total'])" 2>/dev/null || echo -1
}

say "Install the pinned release through the Duckwork CLI"
install_args=(https://github.com/DuckMind/duckwork --ref "$RELEASE_REF")
install_help=$(duckwork plugins install --help 2>/dev/null || true)
# --yes-deps exists on newer Duckwork; older releases prepare dependencies by
# default and reject the unknown flag. --force reinstalls over an existing
# checkout, so retries after a partial run stay deterministic.
if printf '%s' "$install_help" | grep -q -- "--yes-deps"; then install_args+=(--yes-deps); fi
if printf '%s' "$install_help" | grep -q -- "--force"; then install_args+=(--force); fi
duckwork plugins install "${install_args[@]}" </dev/null || fail "plugins install"
duckwork plugins enable qdrant-memory </dev/null || fail "plugins enable"
# The README's interactive flow uses `duckwork memory setup` here; the script
# sets the provider directly instead, which is equivalent for a demo home.
duckwork config set memory.provider qdrant-memory || fail "config set memory.provider"
duckwork qdrant-memory init --existing use || fail "qdrant-memory init"
duckwork qdrant-memory status || fail "qdrant-memory status"
pre=$(memories_total)
if [ "$pre" = "-1" ]; then
  fail "cannot read the demo scope (duckwork-user/duckwork) in $DEMO_HOME"
elif [ "$pre" != "0" ]; then
  fail "the demo scope (duckwork-user/duckwork) is not empty in $DEMO_HOME (count: ${pre}); the demo deletes this scope at the end, so it only runs on an empty scope. Use a fresh demo home."
fi

say "Session 1 — tell Duckwork a preference (the plugin stores it automatically)"
before=$(memories_total)
[ "$before" -ge 0 ] || fail "cannot read the memory store"
run_chat 780 "Please remember: my project codename is ORION-7 and my main deploy node is 10.99.0.2." || fail "session 1 chat"

say "Waiting for the background extraction to land..."
stored=0
for i in $(seq 1 60); do
  total=$(memories_total)
  if [ "$total" -gt "$before" ]; then
    stored=$((total - before))
    echo "  ✓ stored ${stored} new memories (total ${total})"
    break
  fi
  if [ "$total" -lt 0 ]; then echo "  ... list read failed; retrying ($((i*10))s)"
  else echo "  ... waiting ($((i*10))s)"; fi
  sleep 10
done
[ "$stored" -gt 0 ] || fail "the background extraction stored no new memories within 600s"

say "Stored memories — scoped inventory"
duckwork qdrant-memory list --user duckwork-user --agent duckwork || fail "qdrant-memory list"

say "Session 2 — a fresh session recalls the preference"
recall_out=$(run_chat 600 "Search your durable memory: what is my project codename, and which node do I deploy to?") || fail "session 2 chat"
printf '%s\n' "$recall_out"
printf '%s\n' "$recall_out" | grep -q "ORION-7" || fail "the recall did not return the stored codename"

say "Backend — embedded Qdrant, no separate service"
duckwork qdrant-memory stats || true
ls -la "$DUCKWORK_HOME/qdrant-memory/" 2>/dev/null | head -6 || true

say "Lifecycle — export a portable copy"
export_dir=$(mktemp -d "${TMPDIR:-/tmp}/qdrant-demo-export.XXXXXX")
export_file="$export_dir/export.json"
trap 'rm -rf "$export_dir"' EXIT
duckwork qdrant-memory export --output "$export_file" --user duckwork-user --agent duckwork || fail "qdrant-memory export"
head -c 420 "$export_file" || true; echo
rm -rf "$export_dir"
trap - EXIT

say "Lifecycle — scoped deletion with verification"
duckwork qdrant-memory delete-all --user duckwork-user --agent duckwork --confirm || fail "qdrant-memory delete-all"
remaining=$(memories_total)
[ "$remaining" = "0" ] || fail "the scope is not empty after deletion (${remaining} memories)"
duckwork qdrant-memory list --user duckwork-user --agent duckwork || fail "qdrant-memory list"
say "Done — the memory is gone and the scope is empty."
