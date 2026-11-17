"""Make the repo root importable as the ``duckwork_otel`` package.

The plugin is laid out flat at the repository root (``plugin.yaml`` +
``__init__.py``) so ``duckwork plugins install Mandark-droid/duckwork-otel-plugin``
and a plain clone into ``~/.duckwork/plugins/`` work unchanged. Tests import it
as ``duckwork_otel`` — this meta-path finder maps that name to the repo root
without requiring an editable install, and survives the
``sys.modules.pop(...)`` + re-import cycle the adapter tests perform.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PKG = "duckwork_otel"


class _RootPackageFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == _PKG:
            return importlib.util.spec_from_file_location(
                fullname,
                _ROOT / "__init__.py",
                submodule_search_locations=[str(_ROOT)],
            )
        return None


if not any(isinstance(f, _RootPackageFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _RootPackageFinder())
