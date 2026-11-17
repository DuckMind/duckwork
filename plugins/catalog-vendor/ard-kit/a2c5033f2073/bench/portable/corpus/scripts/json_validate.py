#!/usr/bin/env python3
"""Validate that a file parses as JSON and report the first error with its line and column."""
import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: json_validate.py FILE.json", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}")
        return 1
    except OSError as exc:
        print(f"cannot read file: {exc}", file=sys.stderr)
        return 2
    print("valid JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
