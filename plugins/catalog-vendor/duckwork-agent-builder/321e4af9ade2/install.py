"""Install this unified plugin on macOS, Windows, or Linux. No shell scripts."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def default_home():
    try:
        from duckwork_constants import get_duckwork_home
        return get_duckwork_home()
    except ImportError:
        configured = os.environ.get("DUCKWORK_HOME")
        if configured:
            return Path(os.path.expandvars(configured)).expanduser()
        if sys.platform == "win32":
            return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "duckwork"
        return Path.home() / ".duckwork"


def install(source, home, update=False):
    source, home = Path(source).resolve(), Path(home).expanduser().resolve()
    if not (source / "plugin.yaml").is_file() or not (source / "desktop" / "plugin.js").is_file():
        raise ValueError("Run the installer from a complete Duckwork Agent Builder package.")
    parent = home / "plugins"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / "duckwork-agent-builder"
    if target == source:
        return target
    if target.exists() and not update:
        raise FileExistsError("Already installed. Add --update to replace the plugin's code. Your drafts remain in plugin-data.")
    staging = Path(tempfile.mkdtemp(prefix=".agent-builder-", dir=parent))
    backup = None
    try:
        for item in source.iterdir():
            if item.name.startswith(".") or item.name in {"__pycache__", "tests", "node_modules"}:
                continue
            if item.is_dir():
                shutil.copytree(item, staging / item.name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(item, staging / item.name)
        if target.exists():
            backup = parent / (staging.name + "-previous")
            target.rename(backup)
        try:
            staging.rename(target)
        except BaseException:
            if backup:
                backup.rename(target)
            raise
        if backup:
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target


def main():
    parser = argparse.ArgumentParser(description="Install Duckwork Agent Builder")
    parser.add_argument("--home", type=Path, help="Explicit Duckwork home, including a named profile's home")
    parser.add_argument("--update", action="store_true", help="Replace an existing code installation")
    parser.add_argument("--enable", action="store_true", help="Enable the agent component using Duckwork's native CLI")
    args = parser.parse_args()
    home = args.home or default_home()
    target = install(Path(__file__).parent, home, args.update)
    print(f"Installed Duckwork Agent Builder: {target}")
    if args.enable:
        command = shutil.which("duckwork")
        if not command:
            raise SystemExit("Installed. Run `duckwork plugins enable duckwork-agent-builder` from your Duckwork terminal to enable it.")
        env = dict(os.environ, DUCKWORK_HOME=str(home))
        subprocess.run([command, "plugins", "enable", "duckwork-agent-builder"], env=env, check=True, shell=False)
    print("In Duckwork Desktop: Capabilities → Plugins → Duckwork Agent Builder → enable the Desktop component.")
    print("If the backend was already running, reconnect it once so the plugin's API routes are mounted.")


if __name__ == "__main__":
    main()
