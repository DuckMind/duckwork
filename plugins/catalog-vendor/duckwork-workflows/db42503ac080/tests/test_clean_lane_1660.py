#!/usr/bin/env python3
"""est-2ek.1.660: startup clean-lane assert. A re-drive (wf.py run <id>) of a run
whose lane nodes own a git worktree must NOT blindly re-execute onto the dead
child's uncommitted wreckage — the shape that burns an hour before the next
false-green. The runner owns the check at STARTUP (the commit-time _lane_gate
already refuses the hand-off; this is its boot-time twin, mirroring the #80 boot
sweep: blocks admission BEFORE any Popen, typed failure, never a silent continue).

Law: for every agent node that declares `repo: <lane>`, `git status --porcelain
--untracked-files=no` must be EMPTY at boot; dirty => WORKFLOW_FAILED with the
typed error class lane_wreckage naming the dirty files, no child spawn, and the
banking contract printed (git stash push -m … or a patch file under the run dir
at <run>/wip/<node>.patch). Bank the WIP and the re-drive proceeds.

Scan-free law holds: nodes WITHOUT a repo declaration are never scanned
(golden-solo bytes untouched); git-unable lanes fail open like _lane_gate.

Mutation control: removing the _boot_lane_assert call site in main() turns rows
(boot-refusal / dirty-fanout) RED while rows (b)/(c) stay green — the assertions
below then fail on the proceeded spawns.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("runner_clean_lane", ROOT / "wf.py")
assert spec and spec.loader
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)

FAILS = []
def check(name, ok, note=""):
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(note)[:220]) if note and not ok else ""))
    if not ok:
        FAILS.append(name)

FAKE = """#!/usr/bin/env python3
import sys
print("```json\\n{\\"ok\\": true}\\n```")
"""

def fresh(tmp, i):
    """A fresh throwaway git lane + a base commit."""
    lane = tmp / f"lane{i}"
    lane.mkdir()
    subprocess.run(["git", "-C", str(lane), "init", "-q"], check=True)
    (lane / "tracked.txt").write_text("base\n")
    (lane / "child.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(lane), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(lane), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "base"], check=True)
    return lane

def seed_wreckage(lane):
    """The dead attempt's uncommitted WIP on a TRACKED file."""
    (lane / "child.py").write_text("x = 2  # half-finished fix from the dead child\n")

def run_graph(tmp, name, nodes, binary):
    runs = tmp / "workflows"
    r = runs / name
    r.mkdir(parents=True, exist_ok=True)
    (r / "graph.json").write_text(json.dumps({"nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": str(binary), "concurrency": 1}))
    with patch.dict(os.environ, {"DUCKWORK_HOME": str(tmp), "WF_RUNS_ROOT": str(runs)}, clear=False), \
         patch.object(wf, "validate_graph", return_value=None):
        try:
            verdict = wf.main(name)
        except SystemExit as e:
            verdict = f"system_exit:{e.code}"
        if os.path.exists(r / "wf.pid"):
            os.unlink(r / "wf.pid")      # so the next main() in this process treats it dead
        try:
            os.close(wf._LOCK_FD); wf._LOCK_FD = None
        except Exception:
            pass
        return verdict, r

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    binary = tmp / "fake"
    binary.write_text(FAKE)
    binary.chmod(0o755)

    # (a) WRECKAGE at boot: dirty lane refuses the re-drive — typed failure,
    #     dirty files named, banking path printed, NO child ever spawned.
    laneA = fresh(tmp, 0)
    seed_wreckage(laneA)
    fixA = {"id": "fix", "type": "agent", "goal": "redo the fix", "repo": str(laneA)}
    verifyA = {"id": "verify", "type": "agent", "after": ["fix"], "goal": "verify the fix"}
    verdictA, rA = run_graph(tmp, "cl-dirty", [fixA, verifyA], binary)
    refused = (isinstance(verdictA, str) and "wreckage" in verdictA.lower()) \
        or (isinstance(verdictA, str) and verdictA.startswith("system_exit")
            and (rA / "runner_exit.json").exists()
            and "lane_wreckage" in (rA / "runner_exit.json").read_text())
    check("dirty lane blocks admission at boot (typed WORKFLOW verdict, not a spawn)",
          refused, str(verdictA)[:160])
    exit_rec = json.loads((rA / "runner_exit.json").read_text()) if (rA / "runner_exit.json").exists() else {}
    check("boot refusal is typed lane_wreckage",
          "lane_wreckage" in json.dumps(exit_rec), exit_rec)
    ev = (rA / "events.jsonl").read_text() if (rA / "events.jsonl").exists() else ""
    check("boot refusal names the dirty files",
          "child.py" in json.dumps(exit_rec) + ev, (exit_rec, ev[:200]))
    check("boot refusal prints the banking path under the run dir",
          str(Path("wip") / "fix.patch") in json.dumps(exit_rec) + ev
          or "wip" in json.dumps(exit_rec) + ev, exit_rec)
    check("no child spawn record on refusal",
          not (rA / "nodes" / "fix.json").exists() and not (rA / "nodes" / "verify.json").exists(),
          [p.name for p in (rA / "nodes").iterdir()] if (rA / "nodes").exists() else "no nodes dir")
    check("no run.started event was logged past the assert",
          "run.started" not in ev, ev[:200])

    # (b) CLEAN lane boots and proceeds normally.
    laneB = fresh(tmp, 1)
    verdictB, rB = run_graph(tmp, "cl-clean",
                             [{"id": "fix", "type": "agent", "goal": "do it", "repo": str(laneB)}],
                             binary)
    recB = json.loads((rB / "nodes" / "fix.json").read_text()) if (rB / "nodes" / "fix.json").exists() else {}
    check("clean lane proceeds (node commits done)", recB.get("status") == "done", recB or verdictB)

    # (c1) Wreckage BANKED BY COMMIT: the re-drive proceeds.
    laneC = fresh(tmp, 2)
    seed_wreckage(laneC)
    subprocess.run(["git", "-C", str(laneC), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(laneC), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "bank WIP from dead attempt"], check=True)
    _, rC = run_graph(tmp, "cl-banked",
                      [{"id": "fix", "type": "agent", "goal": "continue from banked WIP",
                        "repo": str(laneC)}], binary)
    recC = json.loads((rC / "nodes" / "fix.json").read_text()) if (rC / "nodes" / "fix.json").exists() else {}
    check("banked (committed) WIP lets the re-drive proceed", recC.get("status") == "done", recC)

    # (c2) Wreckage BANKED BY STASH: the re-drive proceeds.
    laneD = fresh(tmp, 3)
    seed_wreckage(laneD)
    subprocess.run(["git", "-C", str(laneD), "stash", "push", "-m",
                    "wf-redrive-cl-stashed"], check=True,
                   capture_output=True)
    _, rD = run_graph(tmp, "cl-stashed",
                      [{"id": "fix", "type": "agent", "goal": "continue from stashed WIP",
                        "repo": str(laneD)}], binary)
    recD = json.loads((rD / "nodes" / "fix.json").read_text()) if (rD / "nodes" / "fix.json").exists() else {}
    check("stashed WIP lets the re-drive proceed", recD.get("status") == "done", recD)

    # (d) untracked scratch never blocks admission (scratch output is normal).
    laneE = fresh(tmp, 4)
    (laneE / "scratch.txt").write_text("out\n")
    _, rE = run_graph(tmp, "cl-untracked",
                      [{"id": "fix", "type": "agent", "goal": "go", "repo": str(laneE)}], binary)
    recE = json.loads((rE / "nodes" / "fix.json").read_text()) if (rE / "nodes" / "fix.json").exists() else {}
    check("untracked files do not block the boot assert", recE.get("status") == "done", recE)

    # (e) fail OPEN: a declared lane git cannot answer for never bricks the run.
    verdictF, rF = run_graph(tmp, "cl-open",
                             [{"id": "fix", "type": "agent", "goal": "go",
                               "repo": str(tmp / "not-a-repo")}], binary)
    recF = json.loads((rF / "nodes" / "fix.json").read_text()) if (rF / "nodes" / "fix.json").exists() else {}
    check("git-unable lane fails open", recF.get("status") == "done", recF or verdictF)

    # (f) scan-free law: NO repo declaration = NO scan (golden-solo bytes
    #     untouched, an unrelated dirty repo under the run dir is ignored).
    rG = tmp / "workflows" / "cl-scanfree"
    wd = rG / "work" / "fix" / "clone"
    wd.mkdir(parents=True)
    subprocess.run(["git", "-C", str(wd.parent), "init", "-q"], check=True)
    (wd / "x.txt").write_text("y\n")
    subprocess.run(["git", "-C", str(wd.parent), "add", "clone/x.txt"], check=True)
    _, rG = run_graph(tmp, "cl-scanfree",
                      [{"id": "fix", "type": "agent", "goal": "plain node"}], binary)
    recG = json.loads((rG / "nodes" / "fix.json").read_text()) if (rG / "nodes" / "fix.json").exists() else {}
    check("no repo declaration = no boot scan, node proceeds", recG.get("status") == "done", recG)

    # (g) the typed class is a member of the closed ERROR_CLASSES set.
    check("lane_wreckage is in ERROR_CLASSES", "lane_wreckage" in wf.ERROR_CLASSES)

print("FAILURES" if FAILS else "ALL PASS")
sys.exit(1 if FAILS else 0)
