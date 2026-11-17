#!/usr/bin/env python3
"""Run the whole test suite with Duckwork importable, safely.

    python3 tests/run_with_duckwork.py        (Windows: py tests\\run_with_duckwork.py)

Why this exists: some tests (tests/test_install_duckwork.py) call Duckwork's own Python functions to create and
delete real profiles. A scratch DUCKWORK_HOME alone does NOT make that safe if the code comes from the real
Duckwork install: that once rewrote the owner's real launchers. So this runner:

1. refuses to use the real install (anything under ~/.duckwork) as the source of Duckwork code. It needs a
   separate clone, named by CABINET_DUCKWORK_SRC (for example CABINET_DUCKWORK_SRC=/path/to/duckwork-agent-clone);
   without it, the tests that need Duckwork are skipped and the rest run;
2. borrows only the interpreter from Duckwork's venv (for its installed packages), never its code;
3. starts the tests with HOME and DUCKWORK_HOME pointed at a temporary folder (tests/_load.py does this
   before anything imports Duckwork), and never runs a ``duckwork`` command;
4. fingerprints the real ~/.duckwork/profiles listing, the real launchers and the real config before and after,
   and fails loudly if any of them changed.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def real_home() -> Path:
    """The person's real home folder: from pwd on macOS and Linux (HOME may point at a sandbox), Path.home() on Windows."""
    try:
        import pwd  # not on Windows, so only imported here

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except ImportError:
        return Path.home()


REAL_HOME = real_home()
REAL_DUCKWORK = REAL_HOME / ".duckwork"
DEFAULT_PY = REAL_DUCKWORK / "duckwork-agent" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
HERE = Path(__file__).resolve().parent


def fingerprint() -> dict[str, str]:
    """What must not change: the profile names, the launchers, the config. Reads only; nothing is opened for writing."""
    out: dict[str, str] = {}
    profiles = REAL_DUCKWORK / "profiles"
    out["profiles"] = ",".join(sorted(p.name for p in profiles.iterdir())) if profiles.is_dir() else ""
    for rel in ("config.yaml", "duckwork-agent/.duckwork/bin/duckwork", "duckwork-agent/.duckwork/bin/duckwork-acp"):
        p = REAL_DUCKWORK / rel
        try:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "absent"
        except OSError:
            out[rel] = "unreadable"
    return out


def main() -> int:
    raw = os.environ.get("CABINET_DUCKWORK_SRC", "").strip()
    src = Path(raw).expanduser().resolve() if raw else None
    py = Path(os.environ.get("CABINET_DUCKWORK_PY") or DEFAULT_PY)
    if src is not None and str(src).startswith(str(REAL_DUCKWORK.resolve())):
        print(f"Refusing: {src} is inside the real ~/.duckwork. Use a separate clone of Duckwork (see CABINET_DUCKWORK_SRC).")
        return 2
    if src is None:
        print("CABINET_DUCKWORK_SRC is not set. Tests that need Duckwork will be skipped; running the rest.")
        env_path = ""
    elif not (src / "duckwork_cli" / "profiles.py").is_file():
        print(f"No Duckwork clone at {src}. Tests that need Duckwork will be skipped; running the rest.")
        env_path = ""
    else:
        env_path = str(src)
    if not py.is_file():
        print(f"No Duckwork interpreter at {py}.")
        return 2
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONDONTWRITEBYTECODE": "1", "DUCKWORK_DISABLE_LAZY_INSTALLS": "1",
           "LANG": "en_US.UTF-8"}
    if env_path:
        env["PYTHONPATH"] = env_path
    if os.environ.get("CABINET_E2E_ALL") == "1":  # every Bot and crew through the real gateway (several minutes)
        env["CABINET_E2E_ALL"] = "1"
    before = fingerprint()
    code = subprocess.run([str(py), "-m", "unittest", "discover", "-s", str(HERE), "-p", "test_*.py", *sys.argv[1:]], env=env, cwd=str(HERE)).returncode
    after = fingerprint()
    if before != after:
        changed = [k for k in before if before[k] != after[k]]
        print(f"FAIL: the real ~/.duckwork changed during the tests: {changed}")
        return 3
    print("The real ~/.duckwork profiles, launchers and config are unchanged.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
