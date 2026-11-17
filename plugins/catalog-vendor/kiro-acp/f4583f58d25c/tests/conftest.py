"""Test bootstrap: put the duckwork-agent repo (and its venv's site-packages) on sys.path.

The plugin imports ``providers`` / ``agent`` from a duckwork-agent checkout. Point
DUCKWORK_REPO at one (defaults to the live checkout). Run with any Python that has
pytest; duckwork third-party deps come from the checkout's venv via sys.path tail.
"""
import os
import sys

DUCKWORK_REPO = os.environ.get("DUCKWORK_REPO", "/Users/lucas/.duckwork/duckwork-agent")
if DUCKWORK_REPO not in sys.path:
    sys.path.insert(0, DUCKWORK_REPO)

_site = os.path.join(DUCKWORK_REPO, "venv", "lib", "python3.11", "site-packages")
if os.path.isdir(_site) and _site not in sys.path:
    sys.path.append(_site)
