#!/usr/bin/env python3
"""Convert a CSV file into a list of JSON records."""
import csv
import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: csv_to_json.py FILE.csv", file=sys.stderr)
        return 2
    with open(sys.argv[1], newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    json.dump(rows, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
