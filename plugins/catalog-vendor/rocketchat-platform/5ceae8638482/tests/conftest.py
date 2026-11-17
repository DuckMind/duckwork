"""Put the selected duckwork-agent checkout on sys.path for adapter imports.

Tests import ``gateway.*`` directly from a Duckwork source checkout. Set
``DUCKWORK_AGENT_PATH`` to that checkout; it defaults to ``../duckwork-agent``.
The checkout must also be installed with pip so Duckwork runtime dependencies are
available; this path setting alone does not install them.
"""

import os
import sys
from pathlib import Path

_DUCKWORK = Path(
    os.environ.get(
        "DUCKWORK_AGENT_PATH",
        Path(__file__).resolve().parents[2] / "duckwork-agent",
    )
).resolve()

if not (_DUCKWORK / "gateway").is_dir():
    raise RuntimeError(
        f"duckwork-agent checkout not found at {_DUCKWORK}. "
        "Clone https://github.com/DuckMind/duckwork and set DUCKWORK_AGENT_PATH."
    )

sys.path.insert(0, str(_DUCKWORK))
