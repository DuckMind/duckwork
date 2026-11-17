#!/usr/bin/env bash
set -euo pipefail

# Stop the gateway first. Use its DUCKWORK_HOME and Python environment.
cd "$(dirname "$0")/.."
python -c 'import runpy; from duckwork_constants import get_duckwork_home; runpy.run_path("migration.py")["migrate"](get_duckwork_home())'
duckwork plugins remove telegram-business-voice-transcriber
duckwork plugins install neoromantic/telesec --enable --yes-deps
