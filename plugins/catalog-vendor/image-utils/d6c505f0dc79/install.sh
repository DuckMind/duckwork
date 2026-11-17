#!/usr/bin/env bash
# Install / enable the Duckwork `image-utils` plugin into Duckwork profiles.
#
# Single source of truth: this checkout. Each profile gets a SYMLINK to it, so an edit here is live
# in every profile (no copy drift) and rollback is one `rm` plus a gateway restart.
#
# No secrets and no config: the plugin has no settings, no config keys and needs no key — enabling it
# in plugins.enabled is the whole installation.
#
# Usage:
#   ./install.sh                      # every profile of this Duckwork root, staged (default last)
#   ./install.sh <profile>            # one profile
#   DUCKWORK_ROOT=/tmp/tmp-home ./install.sh default --no-restart   # dry-ish run for testing
#
# Flags: --no-restart  skip the gateway restart (used by the install self-test)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$HOME/.duckwork"             # the Duckwork default root: one profile per directory
DUCKWORK_ROOT="${DUCKWORK_ROOT:-$DEFAULT_ROOT}"
RESTART=1
PROFILES=()
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=0 ;;
    *) PROFILES+=("$arg") ;;
  esac
done

# Every profile of THIS Duckwork root, non-default first: staged, so an interrupted run has not yet
# touched the default profile the running gateway serves. `duckwork profile list` is the CLI's own
# answer for the default root; the <root>/profiles/<name>/ directories are the filesystem truth
# behind it and are used whenever the CLI is unavailable or DUCKWORK_ROOT is somewhere else.
discover_profiles() {
  local name seen=""
  _emit() {
    case "$1" in
      default) return 0 ;;                     # emitted last: it is always served by the root
      *[!A-Za-z0-9._-]*) return 0 ;;           # headers, rules and column noise
    esac
    case "$seen" in
      *"|$1|"*) return 0 ;;                    # already listed
    esac
    seen="$seen|$1|"
    printf '%s\n' "$1"
  }

  if [ "$DUCKWORK_ROOT" = "$DEFAULT_ROOT" ]; then
    while IFS= read -r name; do
      _emit "$name"
    done < <(duckwork profile list 2>/dev/null | awk 'NR>1 {print $1}')
  fi
  for name in "$DUCKWORK_ROOT"/profiles/*/; do
    [ -d "$name" ] || continue
    _emit "$(basename "${name%/}")"
  done
  printf '%s\n' default
}

if [ ${#PROFILES[@]} -eq 0 ]; then
  while IFS= read -r derived; do PROFILES+=("$derived"); done < <(discover_profiles)
fi

profile_home() {
  case "$1" in
    default|"") echo "$DUCKWORK_ROOT" ;;
    *) echo "$DUCKWORK_ROOT/profiles/$1" ;;
  esac
}

for profile in "${PROFILES[@]}"; do
  home="$(profile_home "$profile")"
  if [ ! -d "$home" ]; then
    echo "!! profile home missing: $home — skipping $profile" >&2
    continue
  fi
  echo "== $profile ($home)"

  mkdir -p "$home/plugins"
  target="$home/plugins/image-utils"
  if [ -L "$target" ]; then
    echo "   symlink already present: $(readlink "$target")"
  elif [ -e "$target" ]; then
    echo "!! $target exists and is not a symlink — refusing to overwrite" >&2
    continue
  else
    ln -s "$SRC" "$target"
    echo "   linked $target -> $SRC"
  fi

  # Always pass -p explicitly when installing into the default root: the bare `duckwork` CLI follows
  # the root's active_profile file. A non-default DUCKWORK_ROOT cannot be reached with -p (profiles are
  # HOME-anchored), so there the CLI is pointed at the home with DUCKWORK_HOME instead.
  # `plugins enable` writes plugins.enabled; no platform_toolsets entry is required in 0.21.3
  # (plugin toolsets are enabled by default on every platform).
  if [ "$DUCKWORK_ROOT" = "$DEFAULT_ROOT" ]; then
    duckwork -p "$profile" plugins enable image-utils --no-allow-tool-override >/dev/null
  else
    env "DUCKWORK_HOME=$home" duckwork plugins enable image-utils --no-allow-tool-override >/dev/null
  fi
  echo "   enabled in plugins.enabled (no tool override, no config keys, no secrets)"

  # Prove exposure through the real discovery path for THIS profile home (not just the file
  # listing): get_definitions is what the model actually sees. Run from the Duckwork source tree so a
  # local tools.py in the plugin dir cannot shadow tools/*.
  SOURCE_DIR="${DUCKWORK_SOURCE:-$DUCKWORK_ROOT/duckwork-agent}"
  if [ ! -d "$SOURCE_DIR" ]; then
    SOURCE_DIR="$DEFAULT_ROOT/duckwork-agent"
  fi
  ( cd "$SOURCE_DIR" && env DUCKWORK_HOME="$home" venv/bin/python - <<'PY'
import json

from duckwork_cli.plugins import discover_plugins
from tools.registry import registry

discover_plugins()
registered = sorted(n for n in registry.get_all_tool_names() if n.startswith("image_"))
exposed = sorted(d["function"]["name"] for d in registry.get_definitions(set(registered)))
print(f"   registered {len(registered)}, exposed {len(exposed)} {exposed}")
if len(exposed) != 6 or registered != exposed:
    raise SystemExit(f"   !! FAIL: expected 6 exposed image tools, got {exposed}")
out = json.loads(registry.dispatch("image_info", {"path": "/nonexistent/self-test.png"}))
assert "pillow_available" in out, out
print(f"   dispatch image_info -> {json.dumps(out)[:150]}")
PY
  ) || exit 1

  if [ "$RESTART" = "1" ]; then
    echo "   restarting the gateway for this profile (best effort)"
    # `duckwork gateway restart` is the supported entry point; it targets this profile's service
    # (the default profile's unit is the one that multiplexes, which is why one restart is enough).
    if [ "$DUCKWORK_ROOT" = "$DEFAULT_ROOT" ]; then
      duckwork -p "$profile" gateway restart \
        || echo "!! could not restart the gateway — start it yourself: duckwork -p $profile gateway restart" >&2
    else
      env "DUCKWORK_HOME=$home" duckwork gateway restart \
        || echo "!! could not restart the gateway — start it yourself (DUCKWORK_HOME=$home)" >&2
    fi
  fi
done

cat <<'MSG'

Verify from a chat: `run image_info on <some photo>` — it answers with the header facts, and its
`pillow_available` field is true when the plugin found Pillow.

Rollback (one profile):
  rm <profile-home>/plugins/image-utils
  duckwork -p <profile> plugins disable image-utils
  duckwork -p <profile> gateway restart

No state outside the files it writes; the plugin keeps no cache, no database and no config.
MSG
