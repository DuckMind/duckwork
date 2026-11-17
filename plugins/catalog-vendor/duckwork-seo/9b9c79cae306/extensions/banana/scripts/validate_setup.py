#!/usr/bin/env python3
"""
Validate the Banana provider prerequisites exposed to this Duckwork process.

Checks:
1. The profile-scoped API key was injected
2. A nonsecret model ID is configured
3. Node.js/npx is available
4. The output directory exists or can be created

Usage:
    python3 validate_setup.py
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"


def check(label: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f": {detail}"
    print(msg)
    return passed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Banana prerequisites in the active Duckwork profile."
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("NANOBANANA_MODEL"),
        help="Nonsecret model ID (or set NANOBANANA_MODEL).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("Banana - Duckwork Profile Validation")
    print("=" * 40)
    results = []

    key = os.environ.get("GOOGLE_AI_API_KEY", "")
    results.append(check(
        "GOOGLE_AI_API_KEY is available",
        bool(key),
        "injected by Duckwork" if key else "missing from active profile",
    ))

    model = args.model or ""
    results.append(check(
        "NANOBANANA_MODEL is set",
        bool(model),
        model or "missing from runtime configuration",
    ))

    # Compatible MCP providers commonly use npx; direct REST helpers do not.
    has_npx = shutil.which("npx") is not None
    results.append(check(
        "npx is available in PATH",
        has_npx,
        shutil.which("npx") or "not found",
    ))

    # Output directory
    if OUTPUT_DIR.exists():
        results.append(check("Output directory exists", True, str(OUTPUT_DIR)))
    else:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            results.append(check("Output directory created", True, str(OUTPUT_DIR)))
        except OSError as e:
            results.append(check("Output directory writable", False, str(e)))

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"Results: {passed}/{total} checks passed")

    if passed == total:
        print("Status: Ready to generate images!")
        return 0
    else:
        print("Status: Some checks failed. Fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
