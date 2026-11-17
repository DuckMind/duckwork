"""Match Duckwork's native YAML policy, retaining legacy standalone support."""
from importlib import import_module

try:
    yaml = import_module("duckwork_yaml")
except ModuleNotFoundError as exc:
    # Only an absent host adapter permits the legacy dependency. A broken
    # adapter/dependency must remain an error, not silently change parsing.
    if exc.name != "duckwork_yaml":
        raise
    yaml = import_module("yaml")
