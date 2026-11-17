#!/usr/bin/env bash
# Entfernt die Session-Flow-Installation aus dem Duckwork-Desktop-Plugin-Ordner.
# Das Repo selbst bleibt unangetastet.
set -euo pipefail

DUCKWORK_HOME="${DUCKWORK_HOME:-$HOME/.duckwork}"
TARGET="$DUCKWORK_HOME/desktop-plugins/session-flow"
: "${TARGET:?}"

if [[ -e "$TARGET" || -L "$TARGET" ]]; then
  rm -rf "$TARGET"
  echo "Entfernt: $TARGET"
else
  echo "Nichts zu entfernen: $TARGET existiert nicht."
fi

echo "In der App ggf.  ⌘K / Ctrl+K  ->  \"Reload desktop plugins\"  ausführen."
