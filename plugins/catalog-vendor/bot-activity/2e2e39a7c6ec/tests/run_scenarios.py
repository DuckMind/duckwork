"""Run every scenario in its own interpreter and report pass/fail.

Each scenario points DUCKWORK_HOME at a fresh temp root and starts the plugin's process-wide
writer, so scenarios must not share a process. They import Duckwork Agent's own modules
(``duckwork_cli``, ``duckwork_constants``, ``agent.redact``), so run this with Duckwork's Python:

    ~/.duckwork/duckwork-agent/venv/bin/python tests/run_scenarios.py [name ...]

No test framework needed. The `duckwork` CLI is mocked in every scenario; nothing touches your
real ~/.duckwork.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def _duckwork_env() -> dict[str, str]:
    """Put the Duckwork source dir on PYTHONPATH, as Duckwork's own launcher does. A venv's editable
    install can predate newer top-level core modules (e.g. ``duckwork_yaml``) and not map them."""
    import duckwork_constants

    source = str(Path(duckwork_constants.__file__).resolve().parent)
    existing = os.environ.get("PYTHONPATH")
    return {**os.environ, "PYTHONPATH": source + (os.pathsep + existing if existing else "")}
SCENARIO_TIMEOUT_S = 180


def main(names: list[str]) -> int:
    scenarios = sorted(SCENARIOS_DIR.glob("*.py"))
    if names:
        scenarios = [s for s in scenarios if s.stem in names]
        if not scenarios:
            print(f"no scenario named {names}; have: {[s.stem for s in sorted(SCENARIOS_DIR.glob('*.py'))]}")
            return 2
    env = _duckwork_env()
    failed = []
    for scenario in scenarios:
        started = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, str(scenario)], capture_output=True, text=True,
                                  timeout=SCENARIO_TIMEOUT_S, env=env)
            ok, output = proc.returncode == 0, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            ok, output = False, f"timed out after {SCENARIO_TIMEOUT_S}s"
        print(f"{'PASS' if ok else 'FAIL'}  {scenario.stem:16s} {time.monotonic() - started:5.1f}s")
        if not ok:
            failed.append(scenario.stem)
            print("\n".join("    " + line for line in output.strip().splitlines()[-30:]))
    print(f"\n{len(scenarios) - len(failed)}/{len(scenarios)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
