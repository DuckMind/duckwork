#!/usr/bin/env python3
"""Send one HTTP request to a URL and print the status code, headers and elapsed time."""
import sys
import time
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: http_probe.py URL", file=sys.stderr)
        return 2
    started = time.perf_counter()
    with urllib.request.urlopen(sys.argv[1], timeout=15) as resp:
        elapsed = (time.perf_counter() - started) * 1000
        print(f"{resp.status} in {elapsed:.0f}ms")
        for key, value in resp.headers.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
