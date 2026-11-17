#!/usr/bin/env python3
"""PR #243 BLOCKING-fix contract (zap review comment 6017431934): a machine gate's
probe is bound to the run that OWNS the gate — never to an ancestor's run dir.

A child runner can be spawned by an agent of an ANCESTOR run (door spawns pass
os.environ through, __init__.py). Agent spawns bake DUCKWORK_WF_RUN_DIR to their
own run (wf.py agent-spawn law), but the machine-gate probe spawn historically
inherited the runner's raw environment — so a nested await-ci-style probe that
prefers DUCKWORK_WF_RUN_DIR read its ANCESTOR's handoff pointer.

Zap's repro, executed here against the SHIPPED await-ci argv (the shipped bytes,
not a paraphrase): child's own pointer is `exit 1` and the ancestor's is
`exit 0`. A real isolated `wf.py run` of a gate-only child graph, with the
inherited parent env, must FAIL on the child's own red CI (last_exit 1) — never
release at attempt 1 with the ancestor's last_exit 0. The mirror case (child
green, ancestor red) must RELEASE: the gate follows the child, not the env.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

ok = 0


def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("PASS", msg)


# The SHIPPED probe bytes — the bug lives in the shipped example + the runner's
# env handling at the gate spawn; testing a paraphrase would test nothing.
SHIPPED = json.loads(
    (ROOT / "examples" / "release" / "release-lifecycle.workflow.json").read_text()
)
AWAIT = next(n for n in SHIPPED["nodes"] if n["id"] == "await-ci")
PROBE_ARGV = list(AWAIT["wait"]["until_argv"])


def mk_pointer(run_dir: Path, cmd: str) -> None:
    """Write the handoff shape the shipped publish node writes: run_dir/
    release-lifecycle-handoff/current -> a dir holding ci_check.txt."""
    handoff = run_dir / "release-lifecycle-handoff" / "h"
    handoff.mkdir(parents=True, exist_ok=True)
    (handoff / "ci_check.txt").write_text(cmd)
    pointer = run_dir / "release-lifecycle-handoff" / "current"
    pointer.write_text(str(handoff) + "\n")


def run_gate_only(tmp: Path, name: str, child_cmd: str, ancestor_cmd: str,
                  inherit: bool):
    """Real `wf.py run` of a gate-only child graph whose until_argv is the
    shipped await-ci probe. The child's own pointer exits per child_cmd; a
    sibling ancestor run dir's pointer exits per ancestor_cmd, and when
    inherit=True the runner env carries DUCKWORK_WF_RUN_DIR=<ancestor dir>
    (exactly the nested-dispatch inheritance the door produces)."""
    home = tmp / f"home-{name}"
    home.mkdir()
    (home / "config.yaml").write_text("model:\n  default: seat-default\n")
    runs = tmp / f"runs-{name}"
    runs.mkdir()
    ancestor = runs / "ancestor"
    ancestor.mkdir()
    mk_pointer(ancestor, ancestor_cmd)

    run = runs / f"20990101-000000-{name}"
    (run / "nodes").mkdir(parents=True)
    (run / "gates").mkdir()
    graph = {"name": name, "nodes": [
        {"id": "await-ci", "type": "gate",
         "wait": {"until_argv": PROBE_ARGV, "every_s": 0.5, "timeout_s": 3}}]}
    (run / "graph.json").write_text(json.dumps(graph))
    (run / "run.json").write_text(json.dumps(
        {"name": name, "duckwork_bin": str(ROOT / "tests" / "fake"),
         "concurrency": 1, "node_timeout": 30,
         "started": "2099-01-01T00:00:00+00:00"}))
    mk_pointer(run, child_cmd)

    env = {**os.environ, "DUCKWORK_HOME": str(home), "WF_RUNS_ROOT": str(runs)}
    if inherit:
        env["DUCKWORK_WF_RUN_DIR"] = str(ancestor)   # the door-passed ancestor pin
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run.name],
                       capture_output=True, text=True, timeout=60, env=env,
                       cwd=str(tmp))
    events = [json.loads(l) for l in
              (run / "events.jsonl").read_text().splitlines()] \
        if (run / "events.jsonl").exists() else []
    parked = json.loads((run / "gates" / "await-ci.parked.json").read_text()) \
        if (run / "gates" / "await-ci.parked.json").exists() else {}
    return p, events, parked, run


with tempfile.TemporaryDirectory(prefix="nested-gate-243-") as tds:
    tmp = Path(tds)

    # --- (a) ZAP'S REPRO: child's CI red, ancestor's green, inherited env.
    # Must FAIL on the CHILD's exit 1 — never release on the ancestor's 0.
    p, ev, parked, run = run_gate_only(tmp, "childred", "exit 1", "exit 0",
                                       inherit=True)
    names = [e["event"] for e in ev]
    check("gate.released" not in names,
          "child-red/ancestor-red-inherited: the gate NEVER released "
          f"(events: {names})")
    check("gate.wait_timeout" in names,
          "child-red/ancestor-red-inherited: the gate timed out on the child's own CI")
    check(parked.get("last_exit") == 1,
          f"child-red/ancestor-red-inherited: probe saw the CHILD's exit 1, "
          f"not the ancestor's 0 (last_exit={parked.get('last_exit')})")
    check(parked.get("attempt", 0) >= 1 and parked.get("state") == "timeout",
          f"child-red/ancestor-red-inherited: repeated the child's own probe "
          f"(attempt={parked.get('attempt')}, state={parked.get('state')})")
    st = wfcommon.run_state(run)
    check(st.get("status") == "failed",
          f"child-red/ancestor-red-inherited: run failed, not done "
          f"(status={st.get('status')})")

    # --- (b) mirror: child's CI green, ancestor's red, inherited env.
    # Must RELEASE — the gate follows the child, not the ancestor pin.
    p, ev, parked, run = run_gate_only(tmp, "childgreen", "exit 0", "exit 1",
                                       inherit=True)
    names = [e["event"] for e in ev]
    rel = next((e for e in ev if e["event"] == "gate.released"), None)
    check(rel is not None and rel.get("by") == "check",
          f"child-green/ancestor-red-inherited: released by the CHILD's own "
          f"green check (events: {names})")
    st = wfcommon.run_state(run)
    check(st.get("status") == "done",
          f"child-green/ancestor-red-inherited: run done (status={st.get('status')})")

    # --- (c) no inheritance at all: same shapes, env never names a run dir
    # (the pre-existing single-run behavior must not move).
    p, ev, parked, run = run_gate_only(tmp, "plain-red", "exit 1", "exit 0",
                                       inherit=False)
    check("gate.wait_timeout" in [e["event"] for e in ev],
          "child-red/no-inherited-env: still fails on its own CI")

print(f"\nnested_gate_run_dir_243: {ok} checks passed")
