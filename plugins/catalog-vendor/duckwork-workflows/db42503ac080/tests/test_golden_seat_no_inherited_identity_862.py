#!/usr/bin/env python3
"""est-2ek.1.862 tripwire: the golden seat never wears the launching agent's
session identity.

Failure mode pinned: an API seat (the agent container, the api_server gateway)
exports DUCKWORK_SESSION_PLATFORM=api_server. tests/11-golden-solo.py built its
child seat as {**os.environ, ...}; the door stamps
run.json.owner.{session_id,ui_session_id,platform} via _session_env, and
normalize() treats only session_id/ui_session_id as volatile — platform stays
under comparison. The frozen baseline (tests/golden_solo/v1.0.15.json) was
captured on a GitHub runner that has no session identity, so owner.platform is
null there: canonical `python3 scripts/suite.py .` on an API-inherited process
dies in test_11_integration_golden.py with exactly six owner.platform
null->api_server diffs while the identical tree is CI-green (reproduce:
`env DUCKWORK_SESSION_PLATFORM=api_server python3 tests/test_11_integration_golden.py`
against a pre-fix tree -> FAILED (failures=1); RC=0 clean).

Two identity channels must close (get_session_env prefers the core ContextVar
when it was ever bound; os.environ is only the fall-through):
  * the harness env strip (DUCKWORK_SESSION_* / DUCKWORK_UI_SESSION_* popped from
    the dict-merged child seat);
  * tests/11-golden-solo.py::_reset_session_context() ->
    gateway.session_context.reset_session_vars() (every var back to _UNSET),
    ImportError-guarded for the standalone plugin host.

Legs:
  (A) THE PIN, end-to-end: the frozen compare under a hostile inherited
      DUCKWORK_SESSION_* env exits 0 and prints the EMPTY-diff line.
  (B) THE CONTROL (the bug): a child that stamps owner the pre-fix way — exec
      the door, act_run, read run.json — under the SAME hostile env and NO
      neutralizer MUST produce owner.platform == 'api_server'. If this ever
      fails, the stamping channel changed under our feet and this file must be
      re-derived, like test_wake_hermetic_env.py's leg (A).
  (C) THE FIX, same shape: the identical child that first calls
      _reset_session_context() and strips the env keys MUST produce owner
      values that normalize() to null (absent or None).
  (D) THE ACCEPTANCE: tests/test_11_integration_golden.py itself, run under
      the hostile inherited env, exits 0.
  (E) STATIC: scripts/suite.py's _base_env strips the identity families
      (suite-level seat law), and the harness's own strip + reset call live in
      11-golden-solo.py — so nobody deletes the pin again.

Hermetic: every child runs under tempfile homes; no estate paths.
usage: python3 tests/test_golden_seat_no_inherited_identity_862.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

checks = 0
failures = 0


def check(name, ok, detail=""):
    global checks, failures
    checks += 1
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    failures += 0 if ok else 1


HOSTILE = {"DUCKWORK_SESSION_PLATFORM": "api_server",
           "DUCKWORK_SESSION_ID": "20260101_000000_hostile",
           "DUCKWORK_UI_SESSION_ID": "hostile-ui"}


def hostile_env(**over):
    e = {k: v for k, v in os.environ.items()
         if not (k.startswith("DUCKWORK_SESSION_") or k.startswith("DUCKWORK_UI_SESSION_"))}
    e.update(HOSTILE)
    e.update(over)
    return e


# (A) the pin, end-to-end: frozen compare under a hostile inherited env.
#     The subprocess must start from a CLEAN env for the identity family, then
#     be re-poisoned — that is exactly what an API seat hands a child.
p = subprocess.run([sys.executable, str(ROOT / "tests" / "11-golden-solo.py"),
                    "compare", str(ROOT), str(ROOT / "tests" / "golden_solo" / "v1.0.15.json")],
                   capture_output=True, text=True, timeout=180,
                   env=hostile_env(), cwd=str(ROOT))
check("(A) frozen golden compare is GREEN under inherited DUCKWORK_SESSION_* (rc=0)",
      p.returncode == 0, (p.stdout + p.stderr)[-800:])
check("(A) compare printed the EMPTY-diff line", "EMPTY diff 6 scenarios" in p.stdout,
      p.stdout[-400:])

# (B)/(C) the stamping channel both ways, through the real door.
CHILD = r'''
import importlib.util, json, os, sys, tempfile
from pathlib import Path
root = Path(sys.argv[1]); neutralize = sys.argv[2] == "1"
sys.path.insert(0, str(root)); sys.path.insert(0, str(root / "tests"))
if neutralize:
    gs_spec = importlib.util.spec_from_file_location("gs862", root / "tests" / "11-golden-solo.py")
    gs = importlib.util.module_from_spec(gs_spec); gs_spec.loader.exec_module(gs)
    gs._reset_session_context()
    for k in [k for k in os.environ if k.startswith("DUCKWORK_SESSION_")
              or k.startswith("DUCKWORK_UI_SESSION_")]:
        os.environ.pop(k, None)
import duckwork_constants as hc
spec = importlib.util.spec_from_file_location("door862", root / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)   # #71: settings.runs_root pinned to the env pin
with tempfile.TemporaryDirectory(prefix="wf862-") as td:
    td = Path(td); home = td / "home"; home.mkdir()
    os.environ["WF_RUNS_ROOT"] = str(home / "workflows")   # the env pin (est-2ek.1.762)
    tok = hc.set_duckwork_home_override(home)
    try:
        started = door.act_run({"graph": {"name": "t862", "nodes": [
            {"id": "a", "type": "agent", "goal": "JSON:{\"result\":\"ok\"}"}]}})
        rid = started["run_id"]
        r = home / "workflows" / rid
        for _ in range(300):
            st = door.act_status({"run_id": rid})
            if st["status"] in ("done", "failed", "stopped", "held") and not st["runner_live"]:
                break
    finally:
        hc.reset_duckwork_home_override(tok)
    owner = json.loads((r / "run.json").read_text()).get("owner", {})
print(json.dumps({"owner": owner}))
'''
for leg, want, neutralize in (("B", "api_server", "0"), ("C", None, "1")):
    cp = subprocess.run([sys.executable, "-c", CHILD, str(ROOT), neutralize],
                        capture_output=True, text=True, timeout=180,
                        env=hostile_env(DUCKWORK_WF_DUCKWORK_BIN=str(ROOT / "tests" / "fake")),
                        cwd=str(ROOT))
    out = cp.stdout.strip().splitlines()
    owner = None
    if out:
        import json as _json
        try:
            owner = _json.loads(out[-1])["owner"]
        except Exception:
            pass
    if leg == "B":
        check("(B) CONTROL: un-neutralized door under hostile env stamps owner.platform='api_server'",
              owner is not None and owner.get("platform") == want,
              f"rc={cp.returncode} owner={owner} err={cp.stderr[-400:]}")
    else:
        check("(C) FIX: neutralized door under the same hostile env stamps no owner identity",
              owner is not None and not owner.get("platform") and not owner.get("session_id")
              and not owner.get("ui_session_id"),
              f"rc={cp.returncode} owner={owner} err={cp.stderr[-400:]}")

# (D) the acceptance from the issue: the golden test itself under the hostile env.
p = subprocess.run([sys.executable, str(ROOT / "tests" / "test_11_integration_golden.py")],
                   capture_output=True, text=True, timeout=240,
                   env=hostile_env(), cwd=str(ROOT))
check("(D) test_11_integration_golden exits 0 under inherited DUCKWORK_SESSION_PLATFORM=api_server",
      p.returncode == 0, (p.stdout + p.stderr)[-800:])

# (E) static: the two pins are present and wired.
solo = (ROOT / "tests" / "11-golden-solo.py").read_text()
check("(E) harness strips DUCKWORK_SESSION_*/DUCKWORK_UI_SESSION_* from the child seat",
      "startswith('DUCKWORK_SESSION_')" in solo and "startswith('DUCKWORK_UI_SESSION_')" in solo
      and "_reset_session_context()" in solo)
check("(E) the reset helper guards the gateway import (standalone host stays status quo)",
      "from gateway.session_context import reset_session_vars" in solo
      and "except ImportError" in solo)
suite = (ROOT / "scripts" / "suite.py").read_text()
check("(E) suite _base_env strips the identity families too (suite-level seat law)",
      "DUCKWORK_SESSION_" in suite and "DUCKWORK_UI_SESSION_" in suite
      and "_NO_SESSION_IDENTITY" in suite)

print(f"DONE golden_seat_no_inherited_identity_862 — {checks - failures}/{checks}"
      + ("" if failures == 0 else f" ({failures} FAIL)"))
sys.exit(0 if failures == 0 else 1)
