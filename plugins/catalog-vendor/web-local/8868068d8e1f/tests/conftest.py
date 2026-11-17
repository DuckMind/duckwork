"""Make the plugin module and a Duckwork checkout importable.

Run with the Python of a Duckwork install (``agent`` / ``tools`` importable), or point
``DUCKWORK_AGENT_REPO`` at a duckwork-agent checkout.
"""
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PLUGIN_ROOT)
_repo = os.environ.get("DUCKWORK_AGENT_REPO")
if _repo:
    sys.path.insert(1, _repo)
