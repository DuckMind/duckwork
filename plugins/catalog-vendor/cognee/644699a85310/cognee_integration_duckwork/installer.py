# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Materialize the Duckwork directory plugin from the installed pip package.

Duckwork discovers memory providers through pip entry points and by scanning
``$DUCKWORK_HOME/plugins/``. The ``cognee-duckwork-install`` console script adds
the directory layout needed for the CLI and dashboard, copied from the wheel.
The full flow:

    pip install cognee-integration-duckwork-agent
    cognee-duckwork-install
    duckwork memory setup

The one file the scanner actually keys on is the plugin root's ``__init__.py``:
Duckwork' ``plugins.memory._is_memory_provider_dir`` skips — silently — any
directory without one (it must mention ``MemoryProvider`` or
``register_memory_provider`` in its first 8KB). Versions 1.0.0–1.2.0 of this
installer never laid that file down, so a pip install produced a plugin Duckwork
ignored while everything reported success (issue #382). It ships in the wheel
as ``_plugin_root/plugin_init.py`` — naming it ``__init__.py`` in place would
turn ``_plugin_root`` into an importable subpackage and change how setuptools
treats its data files — and is written to the target under its real name.

Because Duckwork runs the *copy*, ``pip install -U`` alone changes nothing —
re-run ``cognee-duckwork-install`` after upgrading. ``duckwork cognee status``
warns when the pip package is newer than the installed copy.

The plugin-root files ship inside the package under ``_plugin_root/`` (a wheel
cannot carry files outside its packages); a test pins them byte-identical to
the repository's canonical copies.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .catalog import catalog_name
from .config import resolve_duckwork_home

# Packaged name -> name at the plugin root. plugin_init.py becomes the
# __init__.py that makes the directory discoverable as a memory provider.
_ROOT_FILES = {
    "plugin.yaml": "plugin.yaml",
    "cli.py": "cli.py",
    "after-install.md": "after-install.md",
    "plugin_init.py": "__init__.py",
}


def install(duckwork_home: str | Path | None = None) -> Path:
    """Copy the plugin into ``$DUCKWORK_HOME/plugins/cognee``; return that path."""
    home = resolve_duckwork_home(duckwork_home)
    if home is None:
        # No Duckwork on the path to ask; the documented default.
        home = Path.home() / ".duckwork"
    package_src = Path(__file__).resolve().parent
    root_src = package_src / "_plugin_root"
    missing = [name for name in _ROOT_FILES if not (root_src / name).is_file()]
    if missing:
        raise RuntimeError(
            "packaged plugin files missing (%s) — this looks like a broken or "
            "source-tree install; reinstall the package from PyPI" % ", ".join(missing)
        )

    target = home / "plugins" / "cognee"
    name = catalog_name(target)
    if name:
        raise RuntimeError(
            f"Refusing to overwrite catalog-managed plugin at {target}. "
            f"Run `duckwork plugins update {name}` instead."
        )
    target.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in _ROOT_FILES.items():
        shutil.copyfile(root_src / source_name, target / target_name)

    # Replace the package wholesale so removed modules never linger.
    dest_package = target / package_src.name
    if dest_package.exists():
        shutil.rmtree(dest_package)
    shutil.copytree(
        package_src,
        dest_package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cognee-duckwork-install",
        description="Install the Cognee memory plugin into a Duckwork Agent home.",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="DUCKWORK_HOME to install into (default: auto-detect, else ~/.duckwork)",
    )
    args = parser.parse_args(argv)
    try:
        target = install(args.home)
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Cognee memory plugin installed at {target}")
    print("Next: run `duckwork memory setup` and select `cognee`.")
    print("After a `pip install -U`, re-run `cognee-duckwork-install` to update this copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
