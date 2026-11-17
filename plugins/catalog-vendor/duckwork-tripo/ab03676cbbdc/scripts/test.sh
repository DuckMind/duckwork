#!/usr/bin/env bash
# Run the contract tests against a Duckwork Agent source checkout.
set -euo pipefail

: "${DUCKWORK_SOURCE:?Set DUCKWORK_SOURCE to a Duckwork Agent source checkout}"
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$DUCKWORK_SOURCE/scripts/run_tests.sh" "$PLUGIN_ROOT/tests" "$@"
