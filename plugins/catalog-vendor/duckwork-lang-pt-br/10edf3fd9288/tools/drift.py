#!/usr/bin/env python3
"""Report how far this pack is from duckwork-agent@main and from the latest release.

Runs ``tools/verify_pack.py --json`` once per reference and prints a Markdown
summary.

``--drift`` alarms only on keys the reference *no longer has* — those are ours to
drop and are real stale strings — or on a surface that fails to parse. New
English keys are reported but do not alarm: the key export counts every leaf,
including array/conditional values a language pack cannot carry (a non-text leaf
is rejected by the validator), so a non-zero "new in English" is information for
a human, not proof of work.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY = HERE / "verify_pack.py"
REPO = "Fordex/duckwork-agent"


def latest_release() -> str:
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{REPO}/releases/latest", "--jq", ".tag_name"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout.strip()
        return out or "main"
    except Exception:
        return "main"


def run_report(ref: str) -> dict:
    done = subprocess.run(
        [sys.executable, str(VERIFY), "--json", "--ref", ref, "--repo", REPO],
        capture_output=True,
        text=True,
        cwd=HERE.parent,
    )
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "errors": [done.stderr.strip() or "no JSON"], "surfaces": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drift", action="store_true", help="exit 1 when the pack carries stale keys")
    args = parser.parse_args()

    release = latest_release()
    refs = ["main"] + ([release] if release != "main" else [])
    reports = {ref: run_report(ref) for ref in refs}

    stale = False
    lines = [
        "| reference | surface | keys | coverage | new in English | stale in pack |",
        "|---|---|---|---|---|---|",
    ]
    for ref, report in reports.items():
        for surface, entry in sorted(report.get("surfaces", {}).items()):
            if entry.get("error"):
                lines.append(f"| `{ref}` | {surface} | — | — | — | {entry['error']} |")
                stale = True
                continue
            missing = entry["reference_keys"] - (entry["keys"] - entry["unknown_count"])
            unknown = entry["unknown_count"]
            # Only the newest reference can tell us a key is stale: an older
            # release legitimately lacks everything added after it, so its
            # "unknown" count is us being ahead, not us carrying dead weight.
            if unknown and ref == "main":
                stale = True
            lines.append(
                f"| `{ref}` | {surface} | {entry['keys']} | {entry['coverage']:.1%} | {missing} | {unknown} |"
            )

    print("## duckwork-lang-pt-br - drift report\n")
    print("\n".join(lines))
    print(
        "\n`new in English` = keys the reference has that the pack does not translate (this count"
        " includes\narray/conditional leaves a pack cannot carry) - `stale in pack` = keys the reference"
        " no longer\nhas, which are safe to drop.\n"
    )
    print("**stale keys detected**" if stale else "**in sync**")

    return 1 if (stale and args.drift) else 0


if __name__ == "__main__":
    raise SystemExit(main())
