#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Miguel Euraque

"""Manage the OpenRouter model list exposed by Hopper."""

from __future__ import annotations

import argparse
import base64
import binascii
import os
from pathlib import Path
import sys
import tempfile


DEFAULT_MODELS = [
    "inclusionai/ling-3.0-flash-vl:free",
]


def duckwork_home() -> Path:
    configured = os.environ.get("DUCKWORK_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".duckwork"


def models_file() -> Path:
    configured = os.environ.get("HOPPER_MODELS_FILE")
    if configured:
        return Path(configured).expanduser()
    return duckwork_home() / "plugin-data" / "hopper" / "models.txt"


def validate_model_id(model: str) -> str:
    model = model.strip()
    if not model:
        raise ValueError("empty model ID")
    if model.startswith("#"):
        raise ValueError("comments are not model IDs")
    if any(ch.isspace() for ch in model):
        raise ValueError(f"model ID contains whitespace: {model!r}")
    if "/" not in model:
        raise ValueError(
            f"{model!r} does not look like an OpenRouter model ID "
            "(expected provider/model)"
        )
    return model


def read_models() -> list[str]:
    path = models_file()
    if not path.exists():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        item = raw.strip()
        if not item or item.startswith("#"):
            continue
        try:
            item = validate_model_id(item)
        except ValueError:
            continue
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def write_models(models: list[str]) -> None:
    path = models_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    unique: list[str] = []
    seen: set[str] = set()
    for raw in models:
        model = validate_model_id(raw)
        if model not in seen:
            seen.add(model)
            unique.append(model)

    content = (
        "# Hopper OpenRouter models — one model ID per line.\n"
        "# Blank lines and lines beginning with # are ignored.\n"
        + "\n".join(unique)
        + ("\n" if unique else "")
    )

    fd, tmp_name = tempfile.mkstemp(prefix="models.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def cmd_list(_: argparse.Namespace) -> int:
    current = read_models()
    if not current:
        print("(no models configured)")
        return 0
    for model in current:
        print(model)
    return 0


def cmd_dump(_: argparse.Namespace) -> int:
    """Print only model IDs; empty catalogs produce no output.

    This is intended for Hopper's Desktop half so it can read the catalog
    without interpreting human-friendly CLI status text.
    """
    for model in read_models():
        print(model)
    return 0


def cmd_replace_b64(args: argparse.Namespace) -> int:
    """Replace the catalog from a base64-encoded UTF-8 payload.

    The Desktop plugin calls this helper as an executable file. Keeping user
    data in one opaque argument avoids shell quoting/injection problems and,
    importantly, avoids interpreter -c/-e flags that Duckwork blocks by design.
    """
    try:
        raw = base64.b64decode(args.payload.encode("ascii"), validate=True)
        text = raw.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error) as exc:
        raise ValueError("invalid base64/UTF-8 model payload") from exc

    models: list[str] = []
    seen: set[str] = set()
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        value = raw_line.strip()
        if not value or value.startswith("#"):
            continue
        try:
            value = validate_model_id(value)
        except ValueError as exc:
            raise ValueError(f"line {line_no}: {exc}") from exc
        if value not in seen:
            seen.add(value)
            models.append(value)

    write_models(models)
    print(f"Saved {len(models)} model(s).")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    current = read_models()
    added = 0
    for raw in args.models:
        model = validate_model_id(raw)
        if model not in current:
            current.append(model)
            added += 1
    write_models(current)
    print(f"Added {added} model(s).")
    print(f"Hopper catalog: {models_file()}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    current = read_models()
    targets = {validate_model_id(item) for item in args.models}
    new = [model for model in current if model not in targets]
    removed = len(current) - len(new)
    write_models(new)
    print(f"Removed {removed} model(s).")
    return 0


def cmd_reset(_: argparse.Namespace) -> int:
    write_models(DEFAULT_MODELS)
    print("Restored Hopper's default model.")
    print(f"Hopper catalog: {models_file()}")
    return 0


def cmd_file(_: argparse.Namespace) -> int:
    print(models_file())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage the models exposed by Hopper in Duckwork."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="List configured models")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("dump", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("replace-b64", help=argparse.SUPPRESS)
    p.add_argument("payload")
    p.set_defaults(func=cmd_replace_b64)

    p = sub.add_parser("add", help="Add one or more OpenRouter model IDs")
    p.add_argument("models", nargs="+")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("remove", help="Remove one or more OpenRouter model IDs")
    p.add_argument("models", nargs="+")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("reset", help="Restore Hopper's default model")
    p.set_defaults(func=cmd_reset)

    p = sub.add_parser("file", help="Print the Hopper models.txt path")
    p.set_defaults(func=cmd_file)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
