#!/usr/bin/env python3
"""est-gxjh6 — WORKFLOW_MAX_SEATS must be read FRESH from the .env files.

Base failure: a long-lived runner inherits the environment of the process that
launched it. An operator who sets WORKFLOW_MAX_SEATS in ~/.duckwork/.env after
serve booted is invisible to os.environ.get for the runner's whole life — the
fleet stays silently on SEATS_DEFAULT (the seat_wait mass-death shape) no
matter what the .env says.

Fix contract (wf.py):
  * cap precedence run.json max_seats > env WORKFLOW_MAX_SEATS > .env files
    (profile .env then root .env) > SEATS_DEFAULT;
  * the .env is read at EVERY cap decision — editing it between two calls of
    _max_seats changes the answer without touching the process env;
  * hostile .env lines (garbage, empty, negative, non-numeric, comment) fall
    through to the default chain and never raise.

Run: PYTHONPATH=/opt/duckwork python3 tests/test_seat_cap_dotenv_gxjh6.py
"""
import importlib.util, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-gxjh6"
HOME.mkdir(exist_ok=True)
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ.pop("WORKFLOW_MAX_SEATS", None)
os.environ.pop("DUCKWORK_PROFILE", None)
_spec = importlib.util.spec_from_file_location("hw_gxjh6_cap", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

env = HOME / ".env"

# ---------- (1) no env, no file -> default.
if env.exists(): env.unlink()
check("no .env, no env: SEATS_DEFAULT", wf._max_seats({}) == wf.SEATS_DEFAULT,
      f"got {wf._max_seats({})}")

# ---------- (2) .env lands WITHOUT touching process env (the base failure).
env.write_text("# comment\nOTHER=1\nWORKFLOW_MAX_SEATS=12\n")
check(".env sets cap to 12 with os.environ untouched",
      wf._max_seats({}) == 12 and "WORKFLOW_MAX_SEATS" not in os.environ,
      f"got {wf._max_seats({})}")

# ---------- (3) fresh read per decision: edit between calls changes the answer.
env.write_text("WORKFLOW_MAX_SEATS=8\n")
check("edit lands immediately (fresh read, no restart)", wf._max_seats({}) == 8,
      f"got {wf._max_seats({})}")

# ---------- (4) explicit process env beats the file.
os.environ["WORKFLOW_MAX_SEATS"] = "6"
check("exported env beats .env (6)", wf._max_seats({}) == 6, f"got {wf._max_seats({})}")
os.environ.pop("WORKFLOW_MAX_SEATS")

# ---------- (5) run.json max_seats beats everything.
os.environ["WORKFLOW_MAX_SEATS"] = "6"
check("meta max_seats beats env (2)", wf._max_seats({"max_seats": 2}) == 2,
      f"got {wf._max_seats({'max_seats': 2})}")
os.environ.pop("WORKFLOW_MAX_SEATS")

# ---------- (6) export prefix + inline comment + quotes parse.
env.write_text("export WORKFLOW_MAX_SEATS=9 # fleet knob\n")
check("export prefix + trailing comment -> 9", wf._max_seats({}) == 9,
      f"got {wf._max_seats({})}")
env.write_text("WORKFLOW_MAX_SEATS=\"14\"\n")
check("quoted value -> 14", wf._max_seats({}) == 14, f"got {wf._max_seats({})}")

# ---------- (7) hostile lines fall through to default, never raise.
for junk in ("WORKFLOW_MAX_SEATS=banana", "WORKFLOW_MAX_SEATS=", "WORKFLOW_MAX_SEATS=-3",
             "WORKFLOW_MAX_SEATS", "  # WORKFLOW_MAX_SEATS=7"):
    env.write_text(junk + "\n")
    try:
        r = wf._max_seats({})
    except Exception as e:
        check(f"hostile line {junk!r} raises: {e}", False)
        continue
    check(f"hostile line {junk!r} -> default", r == wf.SEATS_DEFAULT, f"got {r}")

# ---------- (8) profile .env beats root .env.
(HOME / "profiles").mkdir(exist_ok=True)
(HOME / "profiles" / "probe").mkdir(exist_ok=True)
(HOME / "profiles" / "probe" / ".env").write_text("WORKFLOW_MAX_SEATS=10\n")
env.write_text("WORKFLOW_MAX_SEATS=12\n")
os.environ["DUCKWORK_PROFILE"] = "probe"
try:
    check("profile .env wins over root .env (10)", wf._max_seats({}) == 10,
          f"got {wf._max_seats({})}")
finally:
    os.environ.pop("DUCKWORK_PROFILE", None)

# ---------- (9) unreadable file is absent, not fatal.
env.write_text("WORKFLOW_MAX_SEATS=11\n")
try:
    env.chmod(0)
    check("unreadable .env -> default, no raise", wf._max_seats({}) in (wf.SEATS_DEFAULT, 11) )
finally:
    env.chmod(0o644)

print("RESULT:", "OK" if ok else "FAILURES")
sys.exit(0 if ok else 1)
