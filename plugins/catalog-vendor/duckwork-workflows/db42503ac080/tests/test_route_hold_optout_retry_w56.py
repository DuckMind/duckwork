#!/usr/bin/env python3
"""route-hold escalation — require_route:false is HONORED at the commit hold, and a
re-drive never re-fires holds from a contradicted stale receipt (RED on base, GREEN on branch).

Field evidence (escalation key route-hold-ignores-require-route-and-retry-rebakes-proof):
three nodes killed in one wake — two drift-reprobe tallies after two delete-and-
redrive cycles, and a peer node at 22 min whose COMPLETED changes-verdict output
was thrown away. The hold's OWN error text advertises `require_route: false` as
the escape hatch, but the hold checked only `route_verified` presence: the opt-out
was dead code exactly where the operator was pointed to use it. And every node-
record deletion + re-drive re-fired the hold from the durable run-dir receipt
(baked at an earlier submit, long contradicted by observed serves) — the estate
was doing by hand (amend pop vr + delete receipt + delete record) what the runner
should do at the re-drive seam.

Pinned law (wf.py):
  H1  _route_hold with node require_route:false (author opt-out) + a mismatched
      served: the result PASSES (done commits — completed output is not thrown
      away), and the contradicted proof is dropped from the node def.
  H2  the opt-out also resolves through graph `defaults.require_route:false`
      (same law as the door's _require_route_effective precedence).
  H3  NO opt-out: the #25 hold behavior is byte-identical (mismatch fails
      typed route_unavailable; matching / unknown served still passes).
  R1  first spawn is NEVER released from the receipt hold (substitution still
      refused before submit — the est-2ek.1.641 contract is untouched).
  R2  a re-drive (spawn_no > 1) whose run ALREADY died on the route family for
      this node (route_unavailable / route_substitution_denied in events.jsonl)
      clears the node's stale durable receipt + logs node.route_receipt_cleared,
      so the re-drive is not held against a proof reality contradicted.
  R3  a re-drive after a NON-route death (e.g. timeout) does NOT clear: the
      receipt keeps holding substitutions.
Stdlib only; in-process; no network (the seat stub is a script).
"""
import importlib, json, os, sys, tempfile, threading, types
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
_fake_agent = types.ModuleType("agent"); _fake_agent.__path__ = []
_fake_ru = types.ModuleType("agent.retry_utils")
_fake_ru.parse_retry_after_seconds = lambda x: None
sys.modules.setdefault("agent", _fake_agent)
sys.modules.setdefault("agent.retry_utils", _fake_ru)
import wf  # noqa: E402

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  {str(detail)[:400]}" if detail and not cond else ""))
    fails += 0 if cond else 1

HOME = Path(tempfile.mkdtemp(prefix="wf-routehold-"))
RUNS = HOME / "runs"
RUN = RUNS / "rh"
(RUN / "nodes").mkdir(parents=True); (RUN / "gates").mkdir()

def mkrun(name, node):
    r = RUNS / name
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": [node]}))
    return r

PIN = "vendor-a/model-pinned"
BASE_NODE = {"id": "peer", "type": "agent", "goal": "g", "provider": "vendor-a",
             "model": "model-pinned", "route_verified": PIN}
meta = {"_run": RUN, "_spawn_n": {}, "_procs_lock": threading.Lock(), "_procs": {},
        "_stop": threading.Event(), "node_timeout": 15}
(RUN / "graph.json").write_text(json.dumps({"name": "rh", "nodes": [BASE_NODE]}))

# ---- H1: require_route:false + mismatched served -> PASS (escape hatch is live)
n1 = dict(BASE_NODE, require_route=False)
r1 = wf._route_hold(meta, {"status": "done", "served_model": "model-elsewhere"}, n1)
check("H1 require_route:false: mismatched served PASSES the commit hold (opt-out is live code)",
      r1.get("status") == "done" and r1.get("error_class") != "route_unavailable", r1)
check("H1 the contradicted proof is dropped from the node def at hold time",
      "route_verified" not in n1, n1)

# ---- H2: defaults.require_route:false resolves the opt-out (door precedence)
RUN_D = mkrun("rh-defs", BASE_NODE)
meta_d = dict(meta, _run=RUN_D)
r2 = wf._route_hold(meta_d, {"status": "done", "served_model": "model-elsewhere"},
                    dict(BASE_NODE))
# graph defaults WITHOUT a node-level key
(RUN_D / "graph.json").write_text(json.dumps(
    {"name": "rh-defs", "defaults": {"require_route": False}, "nodes": [BASE_NODE]}))
r2b = wf._route_hold(meta_d, {"status": "done", "served_model": "model-elsewhere"},
                     dict(BASE_NODE))
check("H2 graph defaults.require_route:false also skips the hold",
      r2b.get("status") == "done", r2b)

# ---- H3: no opt-out -> #25 byte-identical
r3 = wf._route_hold(meta, {"status": "done", "served_model": "model-elsewhere"},
                    dict(BASE_NODE))
check("H3 no opt-out: mismatch still fails typed route_unavailable",
      r3.get("status") == "failed" and r3.get("error_class") == "route_unavailable", r3)
r4 = wf._route_hold(meta, {"status": "done", "served_model": PIN}, dict(BASE_NODE))
r5 = wf._route_hold(meta, {"status": "done", "served_model": None}, dict(BASE_NODE))
check("H3 matching served passes; unknown (None) still never counted",
      r4.get("status") == "done" and r5.get("status") == "done")

# ---- R group: stale-receipt re-drive law --------------------------------------
STUB = HOME / "duckwork_stub.py"
STUB.write_text("#!/usr/bin/env python3\nimport sys,os\nprint('```json\\n{\"result\": \"ok\"}\\n```')\n")
STUB.chmod(0o755)
LED = HOME / "attempts.ledger"
LED.write_text("")

def fresh_run(name, verified, extra=None):
    node = {"id": "work", "type": "agent", "goal": "do the work",
            "provider": "openai", "model": "m-pinned"}
    if verified:
        node["route_verified"] = verified
    node.update(extra or {})
    r = mkrun(name, node)
    if verified:
        (r / "route_receipts.json").write_text(json.dumps({"work": verified}))
    m = {"_run": r, "duckwork_bin": str(STUB), "_spawn_n": {}, "_procs_lock": threading.Lock(),
         "_procs": {}, "_stop": threading.Event(), "node_timeout": 15}
    return r, node, m

SUB = {"provider": "other-seat", "model": "model-sub"}

# R1: first spawn under a live receipt: substitution still refused
rA, nA, mA = fresh_run("rh-r1", "openai/m-pinned")
rsd1 = wf._route_substitution_refusal(mA, dict(nA, **SUB), 1)
check("R1 first spawn under the receipt still DENIES substitution (641 law untouched)",
      rsd1 is not None and rsd1.get("error_class") == "route_substitution_denied", rsd1)

# R2: run already died on the route family -> the re-drive clears the stale receipt
rB, nB, mB = fresh_run("rh-r2", "openai/m-pinned")
wf.log(rB, "node.failed", node="work", error_class="route_unavailable")
cleared = wf._stale_route_receipt_clear(mB, nB, 2) if hasattr(wf, "_stale_route_receipt_clear") else None
check("R2 re-drive after a route-family death clears the node's stale receipt",
      cleared is True and json.loads((rB / "route_receipts.json").read_text()).get("work") is None,
      (rB / "route_receipts.json").read_text())
check("R2 the re-drive now submits (no refusal) — the hold cannot re-fire from a contradicted proof",
      wf._route_substitution_refusal(mB, dict(nB, **SUB), 2) is None)
check("R2 the clear is loud: node.route_receipt_cleared in events.jsonl",
      any(json.loads(l).get("event") == "node.route_receipt_cleared"
          for l in (rB / "events.jsonl").read_text().splitlines()),
      (rB / "events.jsonl").read_text()[-300:])

# R3: re-drive after a NON-route death keeps the receipt (still holds)
rC, nC, mC = fresh_run("rh-r3", "openai/m-pinned")
wf.log(rC, "node.failed", node="work", error_class="timeout")
if hasattr(wf, "_stale_route_receipt_clear"):
    wf._stale_route_receipt_clear(mC, nC, 2)
check("R3 re-drive after a non-route death: receipt INTACT, substitution still refused",
      json.loads((rC / "route_receipts.json").read_text()).get("work") == "openai/m-pinned"
      and wf._route_substitution_refusal(mC, dict(nC, **SUB), 2) is not None)

# R4: first spawn never clears, even with route-family history from a PRIOR... guard:
#     route-family death present but spawn_no == 1 (first submit of a re-run lane) keeps
#     the receipt — the door re-bakes proofs at submit; only a re-DRIVE releases.
rD, nD, mD = fresh_run("rh-r4", "openai/m-pinned")
wf.log(rD, "node.failed", node="work", error_class="route_substitution_denied")
if hasattr(wf, "_stale_route_receipt_clear"):
    wf._stale_route_receipt_clear(mD, nD, 1)
check("R4 spawn_no==1 never clears (receipt guards the first spawn)",
      json.loads((rD / "route_receipts.json").read_text()).get("work") == "openai/m-pinned")

import shutil; shutil.rmtree(HOME, ignore_errors=True)
print("DONE route_hold_optout_retry", "OK" if fails == 0 else "FAIL")
sys.exit(0 if fails == 0 else 1)
