#!/usr/bin/env python3
"""est-2ek.1.641 — post-admission route substitution is DENIED before submit.

Evidence (runs 20261004-070649-zap-night-est-2ek1562 / 071125 / 072517): the door
proved the pinned route ALIVE at admission (a proved-alive receipt exists for the
lane), yet a subsequent spawn for that lane billed a DIFFERENT model
(claude-opus) — the require_route gate covers the admission ping and #25's commit
hold fires only AFTER the billing happened. Nothing refuses the substitution
BEFORE the spawn.

Law pinned here (RED on base, GREEN on branch) — require_route enforcement
stays EXACTLY as is; this is an additive fail-closed lane receipt:
  B1  spawn 1 with the pinned def (proved-alive at the stub) commits done; the
      lane keeps a proved-alive receipt (run dir route_receipts.json).
  B2  a subsequent spawn for the SAME lane whose effective route differs from
      the receipt (the denied-fallback shape) is refused BEFORE submit, typed
      error_class=route_substitution_denied, and the seat stub logged ZERO
      attempts against the substituted model.
  B3  the same-model ladder respawn (same route) is NEVER denied (receipt is
      not a spawn lock).
  B4  a lane with no proved-alive receipt behaves byte-identically (no new
      gate fires).
  B5  the typed class is in the closed set ERROR_CLASSES.
  B6  require_route: false does NOT opt out of the receipt hold (fail-closed:
      the opt-out governs the admission ping, not a post-admission substitution).
Uses the repo's own in-process run_child harness (test_11_runner_profile shape)
with a recording seat stub — the stub IS the attempt ledger.
"""
import json, os, shutil, sys, tempfile, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wf  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " + label + ("  " + str(detail)[:400] if detail else "")))
    ok = ok and bool(cond)

HOME = Path(tempfile.mkdtemp(prefix="wf-route641-"))
RUNS = HOME / "runs"
RUN = RUNS / "r641"
(RUN / "nodes").mkdir(parents=True)
(RUN / "gates").mkdir()

# The recording seat stub: every spawn appends the -m/--provider it billed to
# the attempt ledger. Zero lines for a model == zero attempts against it.
STUB = HOME / "duckwork_stub.py"
STUB.write_text(
    "#!/usr/bin/env python3\n"
    "import sys, os\n"
    "a = sys.argv[1:]\n"
    "m = a[a.index('-m') + 1] if '-m' in a else 'seat-default'\n"
    "p = a[a.index('--provider') + 1] if '--provider' in a else ''\n"
    "with open(os.environ['WF641_LEDGER'], 'a') as f:\n"
    "    f.write(p + '/' + m + '\\n')\n"
    "print('```json\\n{\"result\": \"ok\"}\\n```')\n"
)
STUB.chmod(0o755)
LEDGER = HOME / "attempts.ledger"

PIN_P, PIN_M, SUB_P, SUB_M = "openai", "m-pinned", "other-seat", "claude-opus"

node = {"id": "work", "type": "agent", "goal": "do the work",
        "provider": PIN_P, "model": PIN_M,
        "route_verified": f"{PIN_P}/{PIN_M}"}     # the door's proved-alive bake
(RUN / "graph.json").write_text(json.dumps({"name": "r641", "nodes": [node]}))

os.environ["WF641_LEDGER"] = str(LEDGER)
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)
meta = {"_run": RUN, "duckwork_bin": str(STUB), "_spawn_n": {},
        "_procs_lock": threading.Lock(), "_procs": {},
        "_stop": threading.Event(), "node_timeout": 15}

def attempts_for(route):
    try:
        return LEDGER.read_text().splitlines().count(route)
    except OSError:
        return 0

# ---- B1: pinned spawn with the proved-alive receipt spawns and commits -------
r1 = wf.run_child(meta, node, {"work": node}, "do the work", "", None,
                  skey="wf:r641:work")
check("B1 pinned spawn under the receipt: runs normally",
      r1.get("status") == "done", r1)
check("B1 the seat stub billed the PINNED route exactly once",
      attempts_for(f"{PIN_P}/{PIN_M}") == 1 and attempts_for(f"{SUB_P}/{SUB_M}") == 0,
      LEDGER.read_text() if LEDGER.exists() else "<no ledger>")
check("B1 the proved-alive receipt is durable in the run dir (route_receipts.json)",
      (RUN / "route_receipts.json").is_file()
      and json.loads((RUN / "route_receipts.json").read_text()).get("work")
          == f"{PIN_P}/{PIN_M}",
      (RUN / "route_receipts.json").read_text() if (RUN / "route_receipts.json").exists() else "missing")

# ---- B2: a subsequent spawn for the lane billed a DIFFERENT model -> typed refusal
sub_node = dict(node, provider=SUB_P, model=SUB_M)     # the denied-fallback shape
r2 = wf.run_child(meta, sub_node, {"work": sub_node}, "do the work", "", None,
                  skey="wf:r641:work")
check("B2 post-admission substitution: refused BEFORE submit with the typed class",
      r2.get("status") == "failed" and r2.get("error_class") == "route_substitution_denied",
      r2)
check("B2 the error names the lane, the receipt, and the would-be route",
      PIN_M in (r2.get("error") or "") and SUB_M in (r2.get("error") or ""),
      r2.get("error"))
check("B2 ZERO attempts against the substituted model (seat stub is the ledger)",
      attempts_for(f"{SUB_P}/{SUB_M}") == 0, LEDGER.read_text())
check("B2 the refusal is loud in events.jsonl",
      any(json.loads(l).get("event") == "node.route_substitution_denied"
          for l in (RUN / "events.jsonl").read_text().splitlines()),
      (RUN / "events.jsonl").read_text()[-400:] if (RUN / "events.jsonl").exists() else "no events")

# ---- B3: same-route ladder respawn rides the receipt, never denied -----------
r3 = wf.run_child(meta, node, {"work": node}, "do the work", "", None,
                  skey="wf:r641:work#2")
check("B3 same-route respawn is NOT denied (receipt != spawn lock)",
      r3.get("status") == "done" and attempts_for(f"{PIN_P}/{PIN_M}") == 2,
      r3)

# ---- B4: no receipt, no new gate (byte-identical legacy behavior) ------------
RUN2 = RUNS / "r641b"
(RUN2 / "nodes").mkdir(parents=True); (RUN2 / "gates").mkdir()
free_node = {"id": "work", "type": "agent", "goal": "do the work",
             "provider": SUB_P, "model": SUB_M}
(RUN2 / "graph.json").write_text(json.dumps({"name": "r641b", "nodes": [free_node]}))
meta2 = dict(meta, _run=RUN2, _spawn_n={}, _procs={}, _procs_lock=threading.Lock(),
             _stop=threading.Event())
LEDGER.write_text("")                      # fresh ledger: this run bills in isolation
r4 = wf.run_child(meta2, free_node, {"work": free_node}, "do the work", "", None)
check("B4 lane with no proved-alive receipt: first spawn is never held (fail-open on absence)",
      r4.get("status") == "done" and attempts_for(f"{SUB_P}/{SUB_M}") == 1,
      r4)

# ---- B5: typed class in the closed set ---------------------------------------
check("B5 route_substitution_denied is a member of the closed set",
      "route_substitution_denied" in wf.ERROR_CLASSES, sorted(wf.ERROR_CLASSES)[:5])

# ---- B6: require_route:false does NOT opt out of the receipt hold -------------
rc_node = dict(node, require_route=False, provider=SUB_P, model=SUB_M)  # opt-out governs the admission ping, not this
r5 = wf.run_child(meta, rc_node, {"work": rc_node}, "do the work", "", None,
                  skey="wf:r641:work#3")
check("B6 require_route:false + substitution under a live receipt: still DENIED",
      r5.get("status") == "failed"
      and r5.get("error_class") == "route_substitution_denied"
      and attempts_for(f"{SUB_P}/{SUB_M}") == 1,   # still only B4's, never this one
      r5)

shutil.rmtree(HOME, ignore_errors=True)
print("RESULT", "GREEN" if ok else "RED")
raise SystemExit(0 if ok else 1)
