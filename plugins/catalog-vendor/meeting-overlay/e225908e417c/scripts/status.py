#!/usr/bin/env python3
"""meeting-mode health check — is the listen daemon alive and the transcript
fresh? Exit 0 = healthy, exit 1 = stale/missing."""
import os
import sys
import time

HOME = os.path.expanduser("~")
ROLLING = os.path.join(HOME, ".duckwork", "meeting-transcript", "rolling.txt")
STALE_SEC = 30.0

if not os.path.exists(ROLLING):
    print("STALE: rolling.txt missing (daemon never ran)")
    sys.exit(1)

mtime = os.path.getmtime(ROLLING)
age = time.time() - mtime
size = os.path.getsize(ROLLING)

if age > STALE_SEC:
    print(f"STALE: rolling.txt last written {age:.0f}s ago (size {size}B) — daemon dead or routing broken")
    sys.exit(1)

print(f"OK: rolling.txt fresh ({age:.0f}s ago, {size}B)")
