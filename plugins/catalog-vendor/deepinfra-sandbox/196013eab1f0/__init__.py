"""Directory-install shim for Duckwork.

`duckwork plugins install deepinfra/deepinfra-duckwork-sandbox` copies this tree into
`~/.duckwork/plugins/deepinfra-sandbox/` and loads the directory beside `plugin.yaml`,
looking for `register()` there. The real code lives in the
`deepinfra_duckwork_sandbox` package (the pip-installable layout), so put this
directory on `sys.path` and re-export from it. The name is prefixed, so it does
not collide with other plugins' modules.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from deepinfra_duckwork_sandbox import DeepInfraProvider, register  # noqa: E402,F401

__all__ = ["DeepInfraProvider", "register"]
