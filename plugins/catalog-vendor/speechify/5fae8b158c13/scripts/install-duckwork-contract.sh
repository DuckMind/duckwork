#!/usr/bin/env bash
# Put a Duckwork Agent checkout into the current uv env so the tests can import
# the real TTSProvider base class. Set DUCKWORK_SRC, or clone duckwork-agent into
# ./duckwork-agent first.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="${DUCKWORK_SRC:-$root/duckwork-agent}"

if [[ ! -f "$src/pyproject.toml" ]]; then
  echo "No Duckwork checkout at $src. Clone https://github.com/DuckMind/duckwork there or set DUCKWORK_SRC." >&2
  exit 1
fi

# Duckwork only supports editable installs. Its core deps are not needed to
# import the provider base class, but duckwork_cli.config needs its yaml pin.
yaml_pin="$(grep -oE 'ruamel\.yaml==[^"; ]+' "$src/pyproject.toml" | head -1)"
uv pip install -e "$src" --no-deps
uv pip install "$yaml_pin"
