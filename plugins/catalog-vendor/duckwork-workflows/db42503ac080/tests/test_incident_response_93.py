#!/usr/bin/env python3
"""Execute the shipped incident probe argv and the real parked-gate loop."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wf  # noqa: E402

GRAPH = json.loads((ROOT / "examples/ops/incident-response.json").read_text())
GATE = next(n for n in GRAPH["nodes"] if n["id"] == "recovery-probe")
CONVERGE = next(n for n in GRAPH["nodes"] if n["id"] == "converge")
# 133387 ask #3: the shipped probe roots under $DUCKWORK_HOME; the IR_STATE_ROOT
# override (read first by the probe) steers tests at the shipped bytes.


def probe_argv(scratch):
    argv = copy.deepcopy(GATE["wait"]["until_argv"])
    # Only steer the example's scratch root (env); run the shipped inline code.
    assert "IR_STATE_ROOT" in argv[2] and "DUCKWORK_HOME" in argv[2]
    return argv


def poll_sequence(root, name, sequence):
    run = root / name
    run.mkdir()
    scratch = run / "scratch"
    scratch.mkdir()
    (run / "run.json").write_text(json.dumps({"name": "INC-93"}))
    rows = []
    for rc in sequence:
        cmd = scratch / "verify_cmd.txt"
        if rc is None:
            cmd.unlink(missing_ok=True)
        else:
            cmd.write_text("exit " + str(rc))
        cp = subprocess.run(probe_argv(scratch), cwd=run, capture_output=True,
                            text=True, timeout=10,
                            env=dict(os.environ, IR_STATE_ROOT=str(scratch)))
        diag = run / "incident-diagnostic.json"
        rows.append({"exit": cp.returncode,
                     "counter": int((scratch / "clear_ticks").read_text()),
                     "marker": (scratch / "probe_broken").exists(),
                     "prev": (scratch / "prev_poll_broken").exists(),
                     "diagnostic": json.loads(diag.read_text()) if diag.exists() else None,
                     "stdout": cp.stdout, "stderr": cp.stderr})
    return rows


def assert_sticky(rows, incident_id):
    assert [r["exit"] for r in rows] == [1, 2, 1, 0], rows
    assert [r["counter"] for r in rows] == [1, 0, 1, 2], rows
    assert [r["marker"] for r in rows] == [False, True, True, False], rows
    assert [r["prev"] for r in rows] == [False, True, False, False], rows
    assert rows[1]["diagnostic"] == {"incident_id": incident_id, "event": "probe_broken",
                                     "marker": "probe_broken", "probe_exit": 2}, rows
    assert rows[2]["diagnostic"] == rows[1]["diagnostic"], rows
    assert rows[0]["diagnostic"] is None and rows[3]["diagnostic"] is None, rows
    assert "probe_broken" in rows[1]["stdout"], rows


def engine_case(root, name, sequence, deadline):
    run = root / ("engine-" + name)
    (run / "gates").mkdir(parents=True)
    (run / "nodes").mkdir()
    scratch = run / "scratch"
    scratch.mkdir()
    (run / "run.json").write_text(json.dumps({"name": "INC-93"}))
    graph = copy.deepcopy(GRAPH)
    gate = next(n for n in graph["nodes"] if n["id"] == "recovery-probe")
    gate["wait"]["until_argv"] = probe_argv(scratch)
    gate["wait"]["every_s"] = .3
    gate["wait"]["timeout_s"] = deadline
    (run / "graph.json").write_text(json.dumps(graph))
    (scratch / "verify_cmd.txt").write_text("exit " + str(sequence[0]))
    # park_gate -> _aux_run inherits os.environ: steer the shipped probe bytes.
    os.environ["IR_STATE_ROOT"] = str(scratch)
    observations = []

    def consume():
        mirror = run / "gates" / "recovery-probe.parked.json"
        if mirror.exists():
            rec = json.loads(mirror.read_text())
            attempt = rec.get("attempt", 0)
            if attempt and (not observations or observations[-1]["attempt"] != attempt):
                diag = run / "incident-diagnostic.json"
                observations.append({"attempt": attempt, "exit": rec["last_exit"],
                                     "stdout": rec["stdout_tail"],
                                     "diagnostic": json.loads(diag.read_text()) if diag.exists() else None})
                (scratch / "verify_cmd.txt").write_text(
                    "exit " + str(sequence[min(attempt, len(sequence) - 1)]))
        return None

    result = wf.park_gate(run, run.name, gate,
                          {n["id"]: n for n in graph["nodes"]}, consume)
    mirror = json.loads((run / "gates" / "recovery-probe.parked.json").read_text())
    diag = run / "incident-diagnostic.json"
    if not observations or observations[-1]["attempt"] != mirror["attempt"]:
        observations.append({"attempt": mirror["attempt"], "exit": mirror["last_exit"],
                             "stdout": mirror["stdout_tail"],
                             "diagnostic": json.loads(diag.read_text()) if diag.exists() else None})
    return result, observations, mirror, json.loads(diag.read_text()) if diag.exists() else None


with tempfile.TemporaryDirectory(prefix="incident-93-") as tmp:
    root = Path(tmp)
    rows = poll_sequence(root, "sticky", [0, 2, 0, 0])
    assert_sticky(rows, "sticky")
    print("PASS clear/broken/clear/clear with counter, sticky marker, incident record")
    missing = poll_sequence(root, "missing", [0, None, 0, 0])
    assert_sticky(missing, "missing")
    print("PASS missing command is a sticky broken probe")
    baseline = poll_sequence(root, "issue86", [1, 0, 0, 1, 0, 0, 2])
    assert [r["exit"] for r in baseline] == [1, 1, 0, 1, 1, 0, 2], baseline
    assert [r["counter"] for r in baseline] == [0, 1, 2, 0, 1, 2, 0], baseline
    assert baseline[-1]["diagnostic"]["marker"] == "probe_broken"
    print("PASS #86 poll table")
    outcome, obs, mirror, diag = engine_case(root, "permanently-broken", [2], 1.15)
    assert outcome == "failed" and mirror["state"] == "timeout", (outcome, mirror)
    assert mirror["last_exit"] == 2 and "probe_broken" in mirror["stdout_tail"], mirror
    assert diag == {"incident_id": "engine-permanently-broken", "event": "probe_broken",
                    "marker": "probe_broken", "probe_exit": 2}, diag
    assert all(r["exit"] == 2 and r["diagnostic"] == diag for r in obs), obs
    assert not (root / "engine-permanently-broken" / "gates" / "recovery-probe.json").exists()
    print("PASS permanent break emits native stdout and bounded run incident diagnostic")
    outcome, obs, mirror, diag = engine_case(root, "healing", [0, 2, 0, 0], 3)
    assert outcome == "released" and [r["exit"] for r in obs] == [1, 2, 1, 0], obs
    assert obs[1]["diagnostic"]["marker"] == "probe_broken" and diag is None, (obs, diag)
    assert not (root / "engine-healing" / "scratch" / "probe_broken").exists()
    print("PASS real parked gate heals on second genuine clear and removes incident record")
    run = root / "inputs"
    run.mkdir()
    (run / "graph.json").write_text(json.dumps(GRAPH))
    outputs = {n["id"]: {"sentinel": "ANSWER_" + n["id"]} for n in GRAPH["nodes"]}
    for n in GRAPH["nodes"]:
        if n["type"] == "gate":
            outputs[n["id"]]["answer"] = "check"
    prompt, error = wf.build_inputs(run, CONVERGE, outputs)
    assert error is None and all("ANSWER_" + n + '"' in prompt for n in
                                 ("resiliency", "mitigate", "triage")), (error, prompt)
    print("PASS converge receives real mitigate and triage ancestor outputs")
