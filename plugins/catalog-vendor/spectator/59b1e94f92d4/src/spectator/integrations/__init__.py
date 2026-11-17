"""Shipped integration templates for supported coding harnesses."""

from __future__ import annotations

import argparse
from importlib.resources import files

_INTEGRATIONS = {
    "claude-code": "claude-code.json",
    "codex": "codex.json",
    "commandcode": "commandcode.json",
    "opencode": "opencode.ts",
    "pi": "pi.ts",
}


def available_integrations() -> tuple[str, ...]:
    """Return the stable integration names exposed by this package."""
    return tuple(_INTEGRATIONS)


def read_integration(harness: str) -> str:
    """Read one packaged integration template as UTF-8 text."""
    try:
        filename = _INTEGRATIONS[harness]
    except KeyError as exc:
        choices = ", ".join(available_integrations())
        raise ValueError(f"unknown integration {harness!r}; choose one of: {choices}") from exc
    return files(__package__).joinpath(filename).read_text(encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectator-integrations",
        description="List or print Spectator Mode harness integration templates.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list bundled integrations")
    show = subparsers.add_parser("show", help="print one template to stdout")
    show.add_argument("harness", choices=available_integrations())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "list":
        print("\n".join(available_integrations()))
        return 0
    if args.command == "show":
        print(read_integration(args.harness), end="")
        return 0
    return 2


__all__ = ["available_integrations", "main", "read_integration"]
