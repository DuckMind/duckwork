"""Pytest configuration — sets up sys.path and duckwork_herald package context."""
import os
import sys
import types
import tempfile
import importlib.util

# Add plugin dir and Duckwork source to sys.path
PLUGIN_DIR = os.environ.get(
    "DUCKWORK_HERALD_PLUGIN_DIR",
    os.path.join(os.path.dirname(__file__), ".."),
)
DUCKWORK_SRC = os.environ.get(
    "DUCKWORK_SOURCE_DIR",
    os.path.expanduser("~/.duckwork/duckwork-agent"),
)
sys.path.insert(0, PLUGIN_DIR)
sys.path.insert(0, DUCKWORK_SRC)

# Set up duckwork_herald package context so relative imports work.
# We register the package and manually load each submodule by file path
# so `from duckwork_herald import tools` works in tests.
pkg = types.ModuleType("duckwork_herald")
pkg.__path__ = [PLUGIN_DIR]
sys.modules["duckwork_herald"] = pkg

# Manually load submodules by file path
for name in ("config", "ledger", "tools", "callback"):
    filepath = os.path.join(PLUGIN_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"duckwork_herald.{name}", filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"duckwork_herald.{name}"] = mod
    spec.loader.exec_module(mod)

# Ensure config exists
os.environ.setdefault("DUCKWORK_HOME", tempfile.mkdtemp())
_cfg_path = os.path.join(os.environ["DUCKWORK_HOME"], "config.yaml")
if not os.path.exists(_cfg_path):
    _state_path = os.path.join(os.environ["DUCKWORK_HOME"], "duckwork-herald-runs.json")
    with open(_cfg_path, "w") as f:
        f.write(f"duckwork_herald:\n  state_file: {_state_path}\n")