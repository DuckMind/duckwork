#!/usr/bin/env python3
"""Google Ads Keyword Planner requires OAuth, unavailable in the catalog build."""

import sys


def main() -> int:
    print(
        "Google Ads Keyword Planner is disabled in this catalog build: "
        "Duckwork does not provide an approved Google OAuth route.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
