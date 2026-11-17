"""Shared test scaffolding.

Two rules this file exists to enforce:

* tests never touch the operator's live plans — the ``hf_home`` fixture (in the
  root ``conftest.py``) points ``HANDFLOW_HOME`` at a tmp dir;
* the registration contract matches the catalog capability probe: a recording
  stub context that records tool/hook names instead of installing anything.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]


class RecordingContext:
    """Stand-in for the plugin context, mirroring the capability probe's stub."""

    plugin_config: Dict[str, Any] = {}
    profile_name = "test"
    plugin_id = "handflow"

    def __init__(self) -> None:
        self.tools: List[str] = []
        self.hooks: List[str] = []
        self.middleware: List[str] = []

    def register_tool(self, name, *args, **kwargs):
        self.tools.append(str(name))

    def register_hook(self, hook_name, callback):
        self.hooks.append(str(hook_name))

    def register_middleware(self, kind, callback):
        self.middleware.append(str(kind))

    def register_command(self, name, *args, **kwargs):
        return None

    def register_cli_command(self, name, *args, **kwargs):
        return None

    def get_config(self, key, default=None):
        return default


def plugin_yaml() -> Dict[str, Any]:
    """The shipped manifest, parsed — the source of the declared capabilities."""
    import yaml

    return yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))


def call(tool, **kwargs) -> Dict[str, Any]:
    """Invoke the agent tool the way the registry does — ``handler(args_dict)``.

    Passing the arguments as one positional dict is not a style choice: the tool
    registry calls ``entry.handler(args, **kw)``, so a handler that only accepts
    keywords works in tests and fails for the agent.
    """
    return json.loads(tool(dict(kwargs)))
