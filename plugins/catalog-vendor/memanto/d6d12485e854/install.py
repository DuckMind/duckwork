"""Install the Memanto plugin into a Duckwork plugins directory.

Duckwork discovers memory providers as *directories* under
``$DUCKWORK_HOME/plugins/<name>/`` (default ``~/.duckwork/plugins``), each holding
an ``__init__.py`` that exposes ``register(ctx)`` plus a ``plugin.yaml``
manifest. This script writes a self-contained ``memanto/`` plugin folder there
by copying :mod:`duckwork_memanto.provider` verbatim as the plugin's
``__init__.py`` — so once installed it only needs the ``memanto`` SDK (declared
in ``plugin.yaml``), not this package.

Usage::

    duckwork-memanto-install                 # install into $DUCKWORK_HOME (or ~/.duckwork)
    duckwork-memanto-install --duckwork-home /path/to/.duckwork
    duckwork-memanto-install --force         # overwrite an existing install
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_PROVIDER_SRC = _PKG_DIR / "provider.py"
_PLUGIN_YAML = _PKG_DIR / "plugin.yaml"
_PLUGIN_README = _PKG_DIR / "PLUGIN_README.md"

_PLUGIN_NAME = "memanto"


def _default_duckwork_home() -> Path:
    env = os.environ.get("DUCKWORK_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".duckwork"


def install(duckwork_home: Path, *, force: bool = False) -> Path:
    """Write the ``memanto`` plugin into ``duckwork_home/plugins`` and return its path."""
    target = duckwork_home / "plugins" / _PLUGIN_NAME
    if target.exists() and not force:
        raise FileExistsError(
            f"{target} already exists. Re-run with --force to overwrite it."
        )
    target.mkdir(parents=True, exist_ok=True)
    # The provider module doubles as the plugin's __init__.py (it exposes
    # register(ctx) and a MemantoMemoryProvider subclass).
    shutil.copyfile(_PROVIDER_SRC, target / "__init__.py")
    shutil.copyfile(_PLUGIN_YAML, target / "plugin.yaml")
    if _PLUGIN_README.exists():
        shutil.copyfile(_PLUGIN_README, target / "README.md")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="duckwork-memanto-install",
        description="Install the Memanto memory-agent plugin into Duckwork.",
    )
    parser.add_argument(
        "--duckwork-home",
        default=None,
        help="Duckwork home directory (default: $DUCKWORK_HOME or ~/.duckwork).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing memanto plugin.",
    )
    args = parser.parse_args(argv)

    duckwork_home = (
        Path(args.duckwork_home).expanduser()
        if args.duckwork_home
        else _default_duckwork_home()
    )
    try:
        target = install(duckwork_home, force=args.force)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Installed the Memanto memory plugin at {target}")
    print("Next steps:")
    print("  1. pip install memanto")
    print("  2. export MOORCHEH_API_KEY=...   (https://console.moorcheh.ai/api-keys)")
    print("  3. duckwork config set memory.provider memanto")
    print("     (or run: duckwork memory setup  →  select 'memanto')")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
