#!/bin/sh
# Installs duckwork-vision-inline on Linux/macOS.
# Copies the plugin into ~/.duckwork/plugins/duckwork-vision-inline and enables it.
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"
DUCKWORK_HOME="${DUCKWORK_HOME:-$HOME/.duckwork}"
DEST="$DUCKWORK_HOME/plugins/duckwork-vision-inline"

mkdir -p "$DEST"
cp "$SRC/__init__.py" "$SRC/plugin.yaml" "$DEST/"
if [ -f "$SRC/README.md" ]; then cp "$SRC/README.md" "$DEST/"; fi
if [ -d "$SRC/docs" ]; then cp -r "$SRC/docs" "$DEST/"; fi
echo "copied plugin to $DEST"

if ! command -v duckwork >/dev/null 2>&1; then
    echo "duckwork is not on PATH. Run this once it is:"
    echo "  duckwork plugins enable duckwork-vision-inline"
    exit 0
fi

if duckwork plugins enable duckwork-vision-inline; then
    echo "enabled. Restart the desktop backend to pick it up:"
    echo "  systemctl --user restart duckwork-dashboard.service"
else
    echo "enable failed. Add 'duckwork-vision-inline' to plugins.enabled in config.yaml by hand."
fi
