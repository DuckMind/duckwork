#!/usr/bin/env sh
# Duckwork Agent shell-hook wrapper for TamaDuckwork.
# Prefers an explicit interpreter, then the repo's own venv, then PATH python3.
set -eu

# Resolve the script directory from the actual file path, not $0 (which may be a symlink).
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SOURCE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)

if [ -n "${TAMADUCKWORK_PY:-}" ]; then
  PY="$TAMADUCKWORK_PY"
elif [ -x "$SOURCE_ROOT/.venv/bin/python" ]; then
  PY="$SOURCE_ROOT/.venv/bin/python"
elif [ -x "$SOURCE_ROOT/venv/bin/python" ]; then
  PY="$SOURCE_ROOT/venv/bin/python"
else
  PY="python3"
fi

exec "$PY" "$SCRIPT_DIR/duckwork_hook.py"
