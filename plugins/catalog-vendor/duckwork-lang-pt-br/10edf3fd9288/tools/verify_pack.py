#!/usr/bin/env python3
"""Verify this pack's pt-br catalogs against the English reference of a Duckwork revision.

Needs no Duckwork install and no clone: the reference files are fetched from the
duckwork-agent repository at ``--ref`` (default ``main``) — the same files
``duckwork plugins validate`` checks a pack against.

Checks
  1. every ``locales/*.yaml`` parses, is a mapping, and every leaf is text
  2. every key exists in the English reference for its surface
  3. core values keep the English ``{placeholder}`` set exactly
  4. ``{0}``-style braces are balanced in every value
  5. no duplicate keys once nested mappings are flattened

Exit code 0 when every check passes, 1 otherwise. ``--json`` prints a
machine-readable report instead of the human summary.

The desktop surface's *values* live in TypeScript (``apps/desktop/src/i18n/en.ts``)
and cannot be read from the key export, so check 3 is core-only; the desktop
catalog's placeholders are verified at build time by ``tools/build-desktop-pack.mjs``,
which has the English bundle in hand.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"
SURFACES = {
    "core": ("locales/pt-br.yaml", "locales/en.yaml"),
    "tui": ("locales/pt-br.tui.yaml", "locales/_keys.tui.json"),
    "desktop": ("locales/pt-br.desktop.yaml", "locales/_keys.desktop.json"),
}
PLACEHOLDER = re.compile(r"\{([0-9]+|[A-Za-z_][A-Za-z0-9_]*)\}")


def fetch(repo: str, ref: str, path: str) -> str:
    url = RAW.format(repo=repo, ref=ref, path=path)
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https host
        return response.read().decode("utf-8-sig")


def flatten(node, prefix: str = "", out: dict | None = None) -> dict:
    flat = {} if out is None else out
    if isinstance(node, dict):
        for key, value in node.items():
            flatten(value, f"{prefix}.{key}" if prefix else str(key), flat)
    elif isinstance(node, str):
        flat[prefix] = node
    return flat


def duplicates(node) -> list[str]:
    """Dotted paths declared twice in the raw document.

    ``yaml.safe_load`` silently keeps the last of a duplicated key, so this runs
    on the composed node tree instead of the parsed mapping.
    """
    found: list[str] = []

    def walk(mapping, path: str) -> None:
        seen: set[str] = set()
        for key_node, value_node in mapping.value:
            key = str(key_node.value)
            dotted = f"{path}.{key}" if path else key
            if key in seen:
                found.append(dotted)
            seen.add(key)
            if getattr(value_node, "id", "") == "mapping":
                walk(value_node, dotted)

    if getattr(node, "id", "") == "mapping":
        walk(node, "")
    return found


def non_text(node, prefix: str = "") -> list[str]:
    if isinstance(node, dict):
        bad: list[str] = []
        for key, value in node.items():
            bad.extend(non_text(value, f"{prefix}.{key}" if prefix else str(key)))
        return bad
    return [] if isinstance(node, str) else [prefix or "<root>"]


def english_keys(repo: str, ref: str, path: str) -> tuple[set[str], dict[str, str]]:
    raw = fetch(repo, ref, path)
    if path.endswith(".json"):
        data = json.loads(raw)
        keys = data if isinstance(data, list) else data["keys"]
        return {str(k) for k in keys}, {}
    values = flatten(yaml.safe_load(raw))
    return set(values), values


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the pt-br language pack")
    parser.add_argument("--repo", default="Fordex/duckwork-agent")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--pack", default=".", help="pack root (holds locales/)")
    parser.add_argument("--min-desktop-coverage", type=float, default=0.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    pack = Path(args.pack).resolve()
    report: dict = {"repo": args.repo, "ref": args.ref, "surfaces": {}, "errors": [], "warnings": []}

    for surface, (pack_path, ref_path) in SURFACES.items():
        entry: dict = {"file": pack_path}
        report["surfaces"][surface] = entry
        path = pack / pack_path
        if not path.is_file():
            report["errors"].append(f"{pack_path}: missing")
            entry["error"] = "missing"
            continue

        text = path.read_text(encoding="utf-8")
        ref_keys, ref_values = english_keys(args.repo, args.ref, ref_path)
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            report["errors"].append(f"{pack_path}: YAML error: {exc}")
            entry["error"] = "parse"
            continue

        bad_leaves = non_text(document)
        if bad_leaves:
            report["errors"].append(
                f"{pack_path}: non-text leaves: {', '.join(sorted(bad_leaves)[:10])}"
            )

        flat = flatten(document)
        unknown = sorted(set(flat) - ref_keys)
        dupes = duplicates(yaml.compose(text))
        entry.update(
            keys=len(flat),
            reference_keys=len(ref_keys),
            unknown=unknown[:25],
            unknown_count=len(unknown),
            duplicates=dupes[:25],
        )
        entry["coverage"] = round(len(set(flat) & ref_keys) / len(ref_keys), 4) if ref_keys else 1.0

        if unknown:
            report["warnings"].append(
                f"{pack_path}: {len(unknown)} key(s) not in the English {surface} catalog "
                f"(ignored at runtime): {', '.join(unknown[:10])}"
            )
        if dupes:
            report["errors"].append(f"{pack_path}: duplicate key(s): {', '.join(dupes[:10])}")

        mismatched: list[dict] = []
        unbalanced: list[str] = []
        for key, value in flat.items():
            found = [m.group(1) for m in PLACEHOLDER.finditer(value)]
            if surface == "core" and key in ref_values:
                expected = [m.group(1) for m in PLACEHOLDER.finditer(ref_values[key])]
                if sorted(found) != sorted(expected):
                    mismatched.append({"key": key, "expected": expected, "found": found})
            if value.count("{") != value.count("}"):
                unbalanced.append(key)

        entry["placeholder_mismatch"] = mismatched[:25]
        entry["placeholder_mismatch_count"] = len(mismatched)
        entry["unbalanced_braces"] = unbalanced[:25]
        if mismatched:
            report["errors"].append(
                f"{pack_path}: {len(mismatched)} placeholder mismatch(es) vs English: "
                + ", ".join(m["key"] for m in mismatched[:5])
            )
        if unbalanced:
            report["errors"].append(
                f"{pack_path}: unbalanced braces in {len(unbalanced)} value(s): "
                + ", ".join(unbalanced[:5])
            )
        if surface == "desktop" and entry["coverage"] < args.min_desktop_coverage:
            report["errors"].append(
                f"{pack_path}: desktop coverage {entry['coverage']:.1%} below "
                f"--min-desktop-coverage {args.min_desktop_coverage:.1%}"
            )

    report["ok"] = not report["errors"]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for surface, entry in report["surfaces"].items():
            if entry.get("error"):
                print(f"x {surface:<8} {entry['file']}: {entry['error']}")
                continue
            print(
                f"- {surface:<8} {entry['file']}: {entry['keys']} key(s), "
                f"{entry['coverage']:.1%} of the English catalog, "
                f"{entry['unknown_count']} unknown, "
                f"{entry['placeholder_mismatch_count']} placeholder mismatch(es)"
            )
        for warning in report["warnings"]:
            print(f"warning: {warning}")
        for error in report["errors"]:
            print(f"error: {error}")
        print("\nPASS" if report["ok"] else "\nFAIL")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
