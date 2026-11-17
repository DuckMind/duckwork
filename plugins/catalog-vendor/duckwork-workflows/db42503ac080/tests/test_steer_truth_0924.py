#!/usr/bin/env python3
"""Feedback #68: steer on a node/run that can never spawn reports HONEST results.
(a) pending node -> still queued (today's good behavior, no regression);
(b) done/failed/skipped node -> REFUSED, error names the state + points at amend;
(c) live runner / live running child -> existing honest wording (next spawn only,
    running child not rewritten) with the steer queued; (d) done/failed/stopped run
    -> refused, why; interrupted (dead runner, unfinished work) stays queueable
    because wait/resume provably consumes the inbox.
Terminal refusals never leave an inbox line behind.
Run: cd tests && /opt/duckwork/.venv/bin/python3 test_steer_truth_0924.py
"""
import importlib.util, json, os, shutil, sys
from pathlib import Path
from unittest.mock import patch

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(BUILD / "home-68")
os.environ["WF_RUNS_ROOT"] = str(BUILD / "home-68" / "workflows")
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("hw68", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
import wfcommon  # same path re-imported; used only for the pure efp() fingerprint

FAKE = str(BUILD / "fake")  # operator-configured launcher for the created runs
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = FAKE

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

HOME68 = Path(os.environ["DUCKWORK_HOME"])
if HOME68.exists(): shutil.rmtree(HOME68)

NODE = lambda i, **kw: dict({"id": i, "type": "agent", "goal": "x"}, **kw)

def make_run(name, nodes, events=None, node_recs=None):
    """Create the run dir through the door with the runner spawn suppressed, then
    stamp run state by hand (events + efp-stamped node records)."""
    with patch.object(door, "_spawn_runner", lambda *a, **k: None):
        res = door.act_run({"graph": {"name": name, "nodes": nodes}})
    r = HOME68 / "workflows" / res["run_id"]
    assert (r / "graph.json").exists(), res
    if events is not None:
        (r / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    if node_recs:
        graph = json.loads((r / "graph.json").read_text())
        byid = {n["id"]: n for n in graph["nodes"]}
        for nid, st in node_recs.items():
            (r / "nodes" / f"{nid}.json").write_text(
                json.dumps({"status": st, "efp": wfcommon.efp(byid, byid[nid])}))
    return res["run_id"], r

# ---- (d) failed RUN: refuse, name the run state, point at amend, no inbox ----
rid, r = make_run("fb68-failed", [NODE("a"), NODE("b", after=["a"])],
                  events=[{"event": "run.failed"}], node_recs={"a": "failed"})
ans = door.act_steer({"run_id": rid, "node": "b", "text": "late nudge"})
check("failed-run steer refused", ans.get("ok") is False, json.dumps(ans))
check("failed-run refusal names the run state and points at amend",
      ans.get("ok") is False and "failed" in ans.get("error", "")
      and "amend" in ans.get("error", ""), json.dumps(ans))
check("failed-run steer wrote no inbox line", not (r / "inbox.jsonl").exists(), ans)

# ---- (d) stopped RUN: same refusal law ----
rid, r = make_run("fb68-stopped", [NODE("a"), NODE("b", after=["a"])],
                  events=[{"event": "run.stopped"}], node_recs={"a": "done"})
ans = door.act_steer({"run_id": rid, "node": "b", "text": "late nudge"})
check("stopped-run steer refused naming state + amend, no queue",
      ans.get("ok") is False and "stopped" in ans.get("error", "")
      and "amend" in ans.get("error", "") and not (r / "inbox.jsonl").exists(), json.dumps(ans))

# ---- (d) done RUN: refused too — nothing left that can ever spawn ----
rid, r = make_run("fb68-done", [NODE("a")], events=[{"event": "run.done"}],
                  node_recs={"a": "done"})
ans = door.act_steer({"run_id": rid, "node": "a", "text": "late nudge"})
check("done-run steer refused naming state + amend, no queue",
      ans.get("ok") is False and "done" in ans.get("error", "")
      and "amend" in ans.get("error", "") and not (r / "inbox.jsonl").exists(), json.dumps(ans))

# ---- interrupted (dead runner, unfinished work): NOT refused — wait/resume
# ---- provably respawns the runner, which then consumes the inbox.
rid, r = make_run("fb68-interrupted", [NODE("a"), NODE("b", after=["a"])],
                  events=[{"event": "run.resumed"}], node_recs={"a": "done"})
st0 = door._common.run_state(r)
check("setup: dead-runner run reads as interrupted", st0["status"] == "interrupted", st0["status"])
ans = door.act_steer({"run_id": rid, "node": "b", "text": "nudge after crash"})
check("interrupted-run steer queues with the wait-to-resume delivery line",
      ans.get("ok") is True and "wait" in ans.get("delivery", ""), json.dumps(ans))
check("interrupted-run steer left its inbox line for the resumed runner",
      (r / "inbox.jsonl").exists())

# ---- (b) terminal NODE states refuse on a NON-terminal run (node branch). A
# ---- free-standing pending node c keeps the run unfinished; for nstate=failed
# ---- the derived run state IS failed, so the refusal legitimately comes from
# ---- the run law — the honest contract (names state + amend, no queue) holds.
for nstate in ("done", "failed", "skipped"):
    rid, r = make_run(f"fb68-node-{nstate}",
                      [NODE("a"), NODE("b", after=["a"]), NODE("c")],
                      events=[{"event": "run.resumed"}], node_recs={"a": nstate})
    st = door._common.run_state(r)
    expect = "failed" if nstate == "failed" else "interrupted"
    check(f"setup: {nstate}-node run is not terminal", st["status"] == expect,
          json.dumps({k: v["status"] for k, v in st["nodes"].items()}))
    ans = door.act_steer({"run_id": rid, "node": "a", "text": "stale nudge"})
    check(f"{nstate}-node steer refused naming state + amend, no queue",
          ans.get("ok") is False and nstate in ans.get("error", "")
          and "amend" in ans.get("error", "") and not (r / "inbox.jsonl").exists(), json.dumps(ans))

# ---- (a) PENDING node on a live runner: keeps today's good behavior (queued).
# ---- The door binds runner_alive at import — patch the door's own name.
rid, r = make_run("fb68-pending", [NODE("a"), NODE("b", after=["a"])])
with patch.object(door, "runner_alive", lambda *a, **k: True):
    ans = door.act_steer({"run_id": rid, "node": "b", "text": "steer-alpha"})
check("pending node still queues (ok True, no regression)", ans.get("ok") is True, json.dumps(ans))
check("live-runner wording is the honest next-spawn/no-rewrite line",
      "next spawn" in ans.get("delivery", "") and "running" in ans.get("delivery", ""),
      json.dumps(ans))
lines = [json.loads(l) for l in (r / "inbox.jsonl").read_text().splitlines()] \
    if (r / "inbox.jsonl").exists() else []
check("inbox carries the steer line for the pending node",
      any(m.get("node") == "b" and m.get("text") == "steer-alpha" for m in lines), lines)

# ---- (c) node with a LIVE running child: existing honest live-child wording.
# ---- run_state runs for real inside the door's own wfcommon copy: patch THAT
# ---- copy's liveness probes, plus the door-bound runner_alive used for delivery.
rid, r = make_run("fb68-livechild", [NODE("a"), NODE("b", after=["a"])])
node_a = NODE("a")
fake_spawn = {"pid": os.getpid(), "skey": f"wf:{rid}:a:live", "attempt": 0,
              "efp": wfcommon.efp({"a": node_a}, node_a)}
with patch.object(door, "runner_alive", lambda *a, **k: True), \
     patch.object(door._common, "runner_alive", lambda *a, **k: True), \
     patch.object(door._common, "_active_spawns", lambda r_, n_, b_: [dict(fake_spawn)]):
    st = door._common.run_state(r)
    check("setup: node reads running (live child)", st["nodes"]["a"]["status"] == "running",
          json.dumps(st["nodes"]["a"]))
    ans = door.act_steer({"run_id": rid, "node": "a", "text": "mid-course correction"})
# A live child is NOT terminal: queued with the honest wording that the running
# child will not be rewritten — steering lands at the NEXT spawn only.
check("live-child steer keeps honest live wording, queued for next spawn only",
      ans.get("ok") is True and "next spawn" in ans.get("delivery", "")
      and "running" in ans.get("delivery", ""), json.dumps(ans))

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
