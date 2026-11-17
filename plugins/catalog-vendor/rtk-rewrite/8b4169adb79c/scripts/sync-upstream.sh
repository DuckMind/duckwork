#!/usr/bin/env bash
# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
# Maintainer helper: re-sync the mirrored agent-side files from upstream rtk-ai/rtk (develop).
# Only __init__.py + tests are mirrored — plugin.yaml, desktop/ and docs/ are maintained here.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="https://github.com/DuckMind/duckwork"
curl -fsSL "$BASE/rtk-rewrite/__init__.py" -o __init__.py
curl -fsSL "$BASE/rtk-rewrite/plugin.yaml" -o upstream/plugin.yaml
curl -fsSL "$BASE/tests/__init__.py" -o tests/__init__.py
curl -fsSL "$BASE/tests/test_rtk_rewrite_plugin.py" -o tests/test_rtk_rewrite_plugin.py

echo "synced from upstream (develop). This overwrites the local tests/ layout fix — re-apply it"
echo "(tests/test_rtk_rewrite_plugin.py, _PLUGIN_CANDIDATES) before committing:"
echo "  git diff && git add -A && git commit -m 'sync: upstream hooks/duckwork'"