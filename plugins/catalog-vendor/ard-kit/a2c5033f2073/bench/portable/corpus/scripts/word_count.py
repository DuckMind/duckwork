#!/usr/bin/env python3
"""Count the words, lines and characters in a text file."""
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: word_count.py FILE", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    print(f"{len(text.split())} words, {lines} lines, {len(text)} characters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
