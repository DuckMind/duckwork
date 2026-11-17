# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""One-command allow/deny transcript. No Duckwork process, no API key.

    python examples/demo.py
    # or: duckwork-tenuo demo
"""

from duckwork_tenuo.demo import main

if __name__ == "__main__":
    raise SystemExit(main())
