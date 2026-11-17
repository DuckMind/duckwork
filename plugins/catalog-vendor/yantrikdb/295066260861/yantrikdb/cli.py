"""``yantrikdb-duckwork`` CLI — expose the pip-installed provider to Duckwork.

Duckwork discovers user-installed memory providers from
``$DUCKWORK_HOME/plugins/<name>/``. Pip installs this package on Python's
import path, but Duckwork' memory-provider discovery is filesystem-based, so
this CLI creates the small bridge:

    pip install yantrikdb-duckwork-plugin
    yantrikdb-duckwork install

By default the bridge is a tiny shim directory at
``$DUCKWORK_HOME/plugins/yantrikdb`` that imports the pip-installed provider
package. This keeps package upgrades in site-packages while avoiding Duckwork'
user-plugin namespace from breaking package-relative imports. Use ``--copy``
to install a physical copy instead.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

DEFAULT_PLUGIN_NAME = "yantrikdb"


def _plugin_source_dir() -> Path:
    """Return the directory of the installed yantrikdb_duckwork_plugin package.

    pyproject.toml maps the on-disk ``yantrikdb/`` directory to the
    importable package name ``yantrikdb_duckwork_plugin``. The provider source
    lives in this package's directory; Duckwork should see it as a plugin named
    ``yantrikdb``.
    """
    return Path(__file__).resolve().parent


def _default_duckwork_home() -> Path:
    """Return the Duckwork home directory used for user-installed plugins."""
    return Path(os.environ.get("DUCKWORK_HOME", Path.home() / ".duckwork")).expanduser().resolve()


def _copy_provider(src: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for entry in src.iterdir():
        if entry.name == "__pycache__":
            continue
        if entry.is_dir():
            shutil.copytree(entry, target / entry.name)
        else:
            shutil.copy2(entry, target / entry.name)


def _install_provider_shim(src: Path, target: Path) -> None:
    """Install a Duckwork-discoverable shim for the pip package.

    Duckwork loads user memory providers under an internal namespace
    (``_duckwork_user_memory.<name>``). Loading the full pip package directory
    directly under that namespace breaks package-relative imports in the
    provider. The shim keeps Duckwork discovery filesystem-based while importing
    the real provider through its normal package name.
    """
    target.mkdir(parents=True, exist_ok=False)
    (target / "__init__.py").write_text(
        '"""Duckwork user-plugin shim for the pip-installed YantrikDB provider."""\n'
        "from yantrikdb_duckwork_plugin import YantrikDBMemoryProvider\n\n\n"
        "def register(ctx):\n"
        "    ctx.register_memory_provider(YantrikDBMemoryProvider())\n",
        encoding="utf-8",
    )
    plugin_yaml = src / "plugin.yaml"
    if plugin_yaml.exists():
        shutil.copy2(plugin_yaml, target / "plugin.yaml")


def _replace_target(target: Path, *, force: bool) -> None:
    if not target.exists() and not target.is_symlink():
        return
    if not force:
        raise FileExistsError(
            f"{target} already exists. Re-run with --force to overwrite, "
            "or remove it first."
        )
    if target.is_symlink() or target.is_file():
        target.unlink()
    else:
        shutil.rmtree(target)


def _install_user_plugin(args: argparse.Namespace) -> int:
    duckwork_home = Path(args.duckwork_home).expanduser().resolve() if args.duckwork_home else _default_duckwork_home()
    plugins_dir = duckwork_home / "plugins"
    target = plugins_dir / DEFAULT_PLUGIN_NAME
    src = _plugin_source_dir()

    plugins_dir.mkdir(parents=True, exist_ok=True)

    try:
        _replace_target(target, force=args.force)
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    if args.copy:
        _copy_provider(src, target)
        action = "copied"
    else:
        _install_provider_shim(src, target)
        action = "registered"

    print(f"{action} yantrikdb plugin into {target}")
    print()
    print("Next steps:")
    print("  1. duckwork config set memory.provider yantrikdb")
    print(f"  2. configure {duckwork_home}/.env if you want to override defaults:")
    print("       YANTRIKDB_MODE=embedded")
    print(f"       YANTRIKDB_DB_PATH={duckwork_home}/yantrikdb-memory.db")
    print("       YANTRIKDB_NAMESPACE=duckwork")
    print("  3. duckwork memory status     # should show: Status: available [OK]")
    print()
    print("Skills (opt-in, v0.3.0+): set YANTRIKDB_SKILLS_ENABLED=true")
    return 0


def _install_legacy_source_tree(args: argparse.Namespace) -> int:
    """Backward-compatible install path for older Duckwork checkouts/docs."""
    duckwork_root = Path(args.duckwork_root).expanduser().resolve()
    plugins_memory = duckwork_root / "plugins" / "memory"
    target = plugins_memory / DEFAULT_PLUGIN_NAME

    if not plugins_memory.is_dir():
        print(
            f"error: {plugins_memory} does not exist — is {duckwork_root} "
            "actually a Duckwork Agent checkout?",
            file=sys.stderr,
        )
        return 2

    try:
        _replace_target(target, force=args.force)
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    _copy_provider(_plugin_source_dir(), target)
    print(f"copied yantrikdb plugin into {target}")
    print()
    print("Next steps:")
    print("  1. duckwork config set memory.provider yantrikdb")
    print("  2. duckwork memory status     # should show: Status: available [OK]")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    if args.duckwork_root:
        return _install_legacy_source_tree(args)
    return _install_user_plugin(args)


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Remove the Duckwork user-plugin registration created by install."""
    duckwork_home = Path(args.duckwork_home).expanduser().resolve() if args.duckwork_home else _default_duckwork_home()
    target = duckwork_home / "plugins" / DEFAULT_PLUGIN_NAME

    if not target.exists() and not target.is_symlink():
        print(f"yantrikdb plugin registration not found at {target}")
        return 0

    if target.is_symlink() or target.is_file():
        target.unlink()
    else:
        shutil.rmtree(target)

    print(f"removed yantrikdb plugin registration from {target}")
    print()
    print("Next steps:")
    print("  1. If YantrikDB is the active provider, choose another provider:")
    print("       duckwork memory setup")
    print("     or disable the external provider:")
    print("       duckwork config set memory.provider null")
    print("  2. Optionally uninstall the pip package from the Duckwork environment:")
    print("       pip uninstall yantrikdb-duckwork-plugin yantrikdb")
    print("  3. Restart Duckwork if it is running as a gateway/service:")
    print("       duckwork gateway restart")
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    """Print the on-disk path of the installed provider source.

    Useful for users who would rather create their own symlink:
        ln -s "$(yantrikdb-duckwork path)" "$DUCKWORK_HOME/plugins/yantrikdb"
    """
    print(_plugin_source_dir())
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    """v0.5 Wave C — open the bundled read-only substrate inspector.

    Loads the substrate via the same config the provider uses (env vars
    + $DUCKWORK_HOME/yantrikdb.json), starts a localhost HTTP server, and
    optionally opens it in the user's browser.
    """
    from . import ui as _ui
    if args.duckwork_home:
        os.environ.setdefault("DUCKWORK_HOME", str(Path(args.duckwork_home).expanduser()))
    try:
        _ui.serve(host=args.host, port=args.port, open_browser=args.open)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 4
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yantrikdb-duckwork",
        description=(
            "Manage the YantrikDB Duckwork memory provider installed via pip. "
            "Duckwork loads memory providers from $DUCKWORK_HOME/plugins/, so this "
            "CLI bridges the pip package to Duckwork' filesystem discovery."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser(
        "install",
        help="register the pip-installed provider with Duckwork",
    )
    p_install.add_argument(
        "duckwork_root",
        nargs="?",
        help=(
            "deprecated: path to a Duckwork Agent checkout. If supplied, the "
            "provider is copied into <duckwork_root>/plugins/memory/yantrikdb. "
            "Omit this argument to install as a user plugin under $DUCKWORK_HOME/plugins/."
        ),
    )
    p_install.add_argument(
        "--duckwork-home",
        type=str,
        default=None,
        help="Duckwork home directory for user-plugin install (default: $DUCKWORK_HOME or ~/.duckwork)",
    )
    p_install.add_argument(
        "--copy",
        action="store_true",
        help="copy the full provider package instead of creating the default lightweight shim",
    )
    p_install.add_argument(
        "-f", "--force",
        action="store_true",
        help="overwrite an existing yantrikdb provider directory or symlink",
    )
    p_install.set_defaults(func=cmd_install)

    p_uninstall = sub.add_parser(
        "uninstall",
        help="remove the Duckwork user-plugin registration",
    )
    p_uninstall.add_argument(
        "--duckwork-home",
        type=str,
        default=None,
        help="Duckwork home directory for user-plugin uninstall (default: $DUCKWORK_HOME or ~/.duckwork)",
    )
    p_uninstall.set_defaults(func=cmd_uninstall)

    p_path = sub.add_parser(
        "path",
        help="print the on-disk path of the installed provider source",
    )
    p_path.set_defaults(func=cmd_path)

    p_ui = sub.add_parser(
        "ui",
        help="open the bundled read-only substrate inspector (v0.5+)",
    )
    p_ui.add_argument("--host", default="127.0.0.1",
                      help="host to bind (default: 127.0.0.1)")
    p_ui.add_argument("--port", type=int, default=8767,
                      help="port to listen on (default: 8767)")
    p_ui.add_argument("--open", action="store_true",
                      help="open the page in the default browser on startup")
    p_ui.add_argument("--duckwork-home", type=str, default=None,
                      help="DUCKWORK_HOME override (default: $DUCKWORK_HOME or ~/.duckwork)")
    p_ui.set_defaults(func=cmd_ui)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
