#!/usr/bin/env python3
"""Compare the Hebrew catalogs with the key sets of a duckwork-agent checkout.

    python tools/sync_keys.py <duckwork-agent checkout>           # report
    python tools/sync_keys.py <duckwork-agent checkout> --fix     # drop stale keys
    python tools/sync_keys.py <duckwork-agent checkout> --missing missing.txt

Per surface it prints how many keys the target has, how many the pack translates,
which pack keys the target no longer has (stale) and which it does not translate
yet (missing). Core strings are also checked for placeholders: a Hebrew value
whose ``{name}`` set differs from English is ignored by Duckwork, so it is reported.
``--fix`` only removes stale keys; translations are never added automatically.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ruamel.yaml import YAML

PACK = Path(__file__).resolve().parent.parent / "locales"
PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_]*(?::[^{}]*)?\}")


def _flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        else:
            flat[path] = value
    return flat


def _load(path: Path) -> dict[str, str]:
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    return _flatten(data)


def _report(surface: str, pack: dict[str, str], target: set[str]) -> tuple[list[str], list[str]]:
    stale = sorted(k for k in pack if k not in target)
    missing = sorted(k for k in target if k not in pack)
    print(f"{surface:8} target {len(target):5}  translated {len(pack) - len(stale):5}  "
          f"stale {len(stale):4}  missing {len(missing):5}")
    return stale, missing


def _drop_flat(path: Path, stale: set[str]) -> None:
    """Remove stale entries from a flat one-entry-per-line catalog, keeping comments."""
    kept = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith('"'):
            key = json.loads(line[: line.index('": ') + 1])
            if key in stale:
                continue
        kept.append(line)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("duckwork_agent", type=Path)
    parser.add_argument("--fix", action="store_true", help="drop stale keys from the flat TUI/Desktop catalogs")
    parser.add_argument("--missing", type=Path, help="write the missing keys of every surface to this file")
    args = parser.parse_args()
    root: Path = args.duckwork_agent
    sys.stdout.reconfigure(encoding="utf-8")

    en_core = _load(root / "locales" / "en.yaml")
    he_core = _load(PACK / "he.yaml")
    stale_core, missing_core = _report("core", he_core, set(en_core))
    bad = [k for k, v in he_core.items()
           if k in en_core and sorted(PLACEHOLDER.findall(v)) != sorted(PLACEHOLDER.findall(en_core[k]))]
    for key in bad:
        print(f"  placeholder mismatch: {key}")

    missing_all = [f"core {k}" for k in missing_core]
    exit_code = 1 if bad else 0
    for surface in ("tui", "desktop"):
        exported = json.loads((root / "locales" / f"_keys.{surface}.json").read_text(encoding="utf-8"))
        target = set(exported["keys"] if isinstance(exported, dict) else exported)
        path = PACK / f"he.{surface}.yaml"
        stale, missing = _report(surface, _load(path), target)
        missing_all += [f"{surface} {k}" for k in missing]
        if args.fix and stale:
            _drop_flat(path, set(stale))
            print(f"  dropped {len(stale)} stale keys from {path.name}")

    if stale_core:
        print(f"  core has {len(stale_core)} stale keys (remove them from he.yaml by hand): {', '.join(stale_core[:10])}")
    if args.missing:
        args.missing.write_text("\n".join(missing_all) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
