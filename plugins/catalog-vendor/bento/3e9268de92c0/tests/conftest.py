"""pytest bootstrap: make ``support`` and ``bento_duckwork`` importable (unittest discovery needs neither)."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
