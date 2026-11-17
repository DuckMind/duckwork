#!/usr/bin/env bash
# GNU/Linux only (GNU readlink required).
# LOCAL uninstall: removes the plugin directory from a target Duckwork home.
# Applied model choices are NEVER undone by removal — see README "Recovery".
#
# Usage: bash scripts/uninstall-local.sh [DUCKWORK_HOME] [--disable]
set -euo pipefail

DISABLE=0
POSITIONAL=()
for ARG in "$@"; do
  case "$ARG" in
    --disable) DISABLE=1 ;;
    --*) echo "uninstall-local: unknown option $ARG" >&2; exit 2 ;;
    *) POSITIONAL+=("$ARG") ;;
  esac
done
if [ "${#POSITIONAL[@]}" -gt 1 ]; then
  echo "Usage: uninstall-local.sh [DUCKWORK_HOME] [--disable]" >&2
  exit 2
fi
TARGET_HOME="${POSITIONAL[0]:-${DUCKWORK_HOME:-}}"
if [ -z "$TARGET_HOME" ]; then
  echo "lab helper: no target home given" >&2
  exit 2
fi
# Resolve the native live home independently of DUCKWORK_HOME (the lab override).
if [ -n "${DUCKWORK_MODEL_SWITCHER_LIVE_HOME:-}" ]; then
  LIVE_INPUT="$DUCKWORK_MODEL_SWITCHER_LIVE_HOME"
elif [ -n "${HOME:-}" ]; then
  LIVE_INPUT="$HOME/.duckwork"
else
  echo "lab helper: cannot determine live home" >&2
  exit 4
fi
LIVE_HOME="$(readlink -m -- "$LIVE_INPUT")"
TARGET_HOME="$(readlink -m -- "$TARGET_HOME")"
case "$TARGET_HOME/" in "$LIVE_HOME/"|"$LIVE_HOME/"*)
  echo "lab helper: refusing live home or its descendants" >&2; exit 3;;
esac
case "$LIVE_HOME/" in "$TARGET_HOME/"*)
  echo "lab helper: refusing an ancestor of the live home" >&2; exit 3;;
esac
DEST="$TARGET_HOME/plugins/duckwork-model-switcher"
# Do not let a redirected plugins directory turn lab deletion into external deletion.
CHECK_PATH="$DEST"
while [ "$CHECK_PATH" != "/" ]; do
  if [ -L "$CHECK_PATH" ]; then
    echo "lab helper: refusing symlinked destination" >&2; exit 3
  fi
  CHECK_PATH="$(dirname -- "$CHECK_PATH")"
done
RESOLVED_DEST="$(readlink -m -- "$DEST")"
if [ "$RESOLVED_DEST" != "$DEST" ]; then
  echo "lab helper: destination escapes the lab home" >&2; exit 3
fi

if [ ! -d "$DEST" ]; then
  echo "uninstall-local: $DEST not installed" >&2
  exit 1
fi
# D4: disable BEFORE removing the tree — `duckwork plugins disable` cannot
# resolve the plugin once its directory is gone.
if [ "$DISABLE" = 1 ]; then
  if ! command -v duckwork >/dev/null 2>&1; then
    echo "uninstall-local: --disable needs the duckwork CLI on PATH; disable manually with:" >&2
    echo "  DUCKWORK_HOME=\"$TARGET_HOME\" duckwork plugins disable duckwork-model-switcher" >&2
    exit 6
  fi
  if ! DUCKWORK_HOME="$TARGET_HOME" duckwork plugins disable duckwork-model-switcher; then
    echo "uninstall-local: duckwork plugins disable failed; disable manually with:" >&2
    echo "  DUCKWORK_HOME=\"$TARGET_HOME\" duckwork plugins disable duckwork-model-switcher" >&2
    exit 7
  fi
fi
# Preserve the plugin files for explicit recovery after uninstall.
BACKUP="$(mktemp -d -- "$TARGET_HOME/.model-switcher-removed.XXXXXXXX")"
mv -- "$DEST" "$BACKUP/plugin"
echo "uninstalled $DEST; plugin files preserved at $BACKUP/plugin (model choices unchanged)"
# D3 truth: the operation journal and presets do NOT live in the plugin tree —
# they stay at <home>/state/duckwork-model-switcher and are left in place here.
echo "uninstall-local: operation journal/presets are untouched at $TARGET_HOME/state/duckwork-model-switcher"
if [ "$DISABLE" != 1 ]; then
  echo "uninstall-local: if the plugin was enabled, its name stays in plugins.enabled (ignored with a warning); pass --disable to remove it"
fi
