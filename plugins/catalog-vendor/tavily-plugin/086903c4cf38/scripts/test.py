"""Run package integration checks against a supplied Duckwork checkout."""

import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckwork-source", type=Path, required=True)
    args = parser.parse_args()
    source = args.duckwork_source.resolve()
    if not (source / "duckwork_cli" / "agent_plugins.py").is_file():
        parser.error("--duckwork-source must point to a Duckwork checkout")
    sys.path.insert(0, str(source))
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="tavily-duckwork-tests-") as home:
        os.environ["DUCKWORK_HOME"] = home
        os.environ["DUCKWORK_RUNTIME_DIR"] = str(Path(home) / "runtime")
        suite = unittest.defaultTestLoader.discover(str(root / "tests"))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
