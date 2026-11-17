from __future__ import annotations

import argparse
import shutil
from pathlib import Path

def duckwork_home() -> Path:
    try:
        from duckwork_constants import get_duckwork_home
        return Path(get_duckwork_home())
    except Exception:
        return Path.home() / ".duckwork"

def main() -> int:
    parser = argparse.ArgumentParser(description="Install bundled theia-ui-computer-use skill into the active Duckwork profile")
    parser.add_argument("--force", action="store_true", help="replace an existing skill directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "skills" / "theia-ui-computer-use"
    target = duckwork_home() / "skills" / "desktop" / "theia-ui-computer-use"
    if not source.exists():
        print(f"ERROR: missing bundled skill: {source}")
        return 2
    if target.exists():
        if not args.force:
            print(f"exists: {target}")
            print("Use --force to replace it.")
            return 0
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    print(f"installed: {target}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
