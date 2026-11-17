#!/usr/bin/env python3
"""Digest 29d (64c6772b): a node that declares `repo: <lane>` may not commit done/partial
while the lane still has uncommitted TRACKED changes — the dad50be0 false-green shape
(fix green but uncommitted at max_turns; downstream verify tested a HEAD equal to the
mutant). The RUNNER owns the check; an author-side 'commit early' law is not trusted.
Mutation control: removing the two `_lane_gate` call sites (solo + fan-out) turns rows
(dirty refused / fan-out refused) RED."""
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
# est-2ek.1.762: shared launch-env pin helper, exec-loaded by file path (repo
# convention — a top-level import of a tests/fixtures module would break the
# test_packaging import-closure from the unpacked package root).
_spec_iso762 = importlib.util.spec_from_file_location(
    "wf_spawn_isolation_762", Path(__file__).parent / "fixtures" / "wf_spawn_isolation_762.py")
assert _spec_iso762 and _spec_iso762.loader
_iso762 = importlib.util.module_from_spec(_spec_iso762)
_spec_iso762.loader.exec_module(_iso762)
pin_env = _iso762.pin_env
spec = importlib.util.spec_from_file_location("runner_lane_gate", ROOT / "wf.py")
assert spec and spec.loader
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)

FAILS = []
def check(name, ok, note=""):
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(note)[:200]) if note and not ok else ""))
    if not ok:
        FAILS.append(name)

FAKE = """#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path
args = sys.argv[1:]
q = open(args[args.index("--query-file") + 1]).read() if "--query-file" in args else ""
lane = next((t.split("=", 1)[1] for t in q.split() if t.startswith("LANE=")), None)
if lane:
    if "DIRTY" in q:
        (Path(lane) / "tracked.txt").write_text("fix\\n")
    elif "COMMIT" in q:
        (Path(lane) / "tracked.txt").write_text("fix\\n")
        subprocess.run(["git", "-C", lane, "add", "-A"], check=True)
        subprocess.run(["git", "-C", lane, "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-m", "banked"], check=True)
    elif "UNTRACKED" in q:
        (Path(lane) / "scratch.txt").write_text("out\\n")
print("```json\\n{\\"ok\\": true}\\n```")
"""

def fresh(tmp, i):
    """A fresh throwaway git lane + a fresh run dir under <tmp>/runs/<name>."""
    lane = tmp / f"lane{i}"
    lane.mkdir()
    subprocess.run(["git", "-C", str(lane), "init", "-q"], check=True)
    (lane / "tracked.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(lane), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(lane), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "base"], check=True)
    return lane

def run_graph(tmp, name, nodes, binary):
    runs = tmp / "workflows"
    r = runs / name
    r.mkdir(parents=True, exist_ok=True)
    (r / "graph.json").write_text(json.dumps({"nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": str(binary), "concurrency": 1}))
    with patch.dict(os.environ, pin_env(dict(os.environ, DUCKWORK_HOME=str(tmp)),
                                        runs, home=tmp), clear=True), \
         patch.object(wf, "validate_graph", return_value=None):
        verdict = wf.main(name)
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

    # (a) DIRTY lane: done refused -> failed incomplete_work + porcelain + downstream blocked
    lane = fresh(tmp, 0)
    fix = {"id": "fix", "type": "agent", "goal": "DIRTY make it so LANE=%s" % lane, "repo": str(lane)}
    verify = {"id": "verify", "type": "agent", "after": ["fix"], "goal": "verify the fix"}
    verdict, r = run_graph(tmp, "lg-dirty", [fix, verify], binary)
    rec = json.loads((r / "nodes" / "fix.json").read_text())
    check("dirty lane refuses the done hand-off",
          rec["status"] == "failed" and rec["error_class"] == "incomplete_work", rec)
    check("refusal carries the porcelain",
          any("tracked.txt" in l for l in rec.get("lane_dirty", [])), rec.get("lane_dirty"))
    check("downstream never consumes an uncommitted fix (run blocks, verify never spawns)",
          verdict == "blocked by failed fix" and not (r / "nodes" / "verify.json").exists(),
          str(verdict)[:120])

    # (b) CLEAN lane (the child committed): done commits as normal
    lane2 = fresh(tmp, 1)
    fix2 = {"id": "fix", "type": "agent", "goal": "COMMIT make it so LANE=%s" % lane2, "repo": str(lane2)}
    _, r2 = run_graph(tmp, "lg-clean", [fix2], binary)
    rec2 = json.loads((r2 / "nodes" / "fix.json").read_text())
    check("committed lane still commits done", rec2["status"] == "done", rec2)

    # (c) untracked scratch NEVER dirties a lane (scratch output is normal child life)
    lane3 = fresh(tmp, 2)
    fix3 = {"id": "fix", "type": "agent", "goal": "UNTRACKED scratch only LANE=%s" % lane3, "repo": str(lane3)}
    _, r3 = run_graph(tmp, "lg-untracked", [fix3], binary)
    rec3 = json.loads((r3 / "nodes" / "fix.json").read_text())
    check("untracked output does not refuse the node", rec3["status"] == "done", rec3)

    # (d) fail OPEN: a lane git cannot answer for (missing path) never bricks the run
    fix4 = {"id": "fix", "type": "agent", "goal": "no lane here",
            "repo": str(tmp / "not-a-repo")}
    _, r4 = run_graph(tmp, "lg-open", [fix4], binary)
    rec4 = json.loads((r4 / "nodes" / "fix.json").read_text())
    check("git-unable fails open", rec4["status"] == "done", rec4)

    # (e) default-off: NO declaration -> NO scan (an unrelated dirty repo in the run
    #     work dir must not ghost-refuse a done node) — the golden-solo law.
    r5 = tmp / "workflows" / "lg-scanfree"
    wd = r5 / "work" / "fix" / "clone"
    wd.mkdir(parents=True)
    subprocess.run(["git", "-C", str(wd.parent), "init", "-q"], check=True)
    (wd / "x.txt").write_text("y\n")          # staged = dirty, in a repo under work/fix/
    subprocess.run(["git", "-C", str(wd.parent), "add", "clone/x.txt"], check=True)
    verdict5, r5 = run_graph(tmp, "lg-scanfree",
                             [{"id": "fix", "type": "agent", "goal": "plain node"}], binary)
    rec5 = json.loads((r5 / "nodes" / "fix.json").read_text())
    check("no repo declaration = no scan, node commits done", rec5["status"] == "done", rec5)

    # (f) fan-out commit site shares the gate (same law, merged record)
    lane6 = fresh(tmp, 6)
    fo = {"id": "build", "type": "agent", "repo": str(lane6), "goal": "build",
          "fanout": {"items": [{"goal": "DIRTY item one LANE=%s" % lane6}]}}
    _, r6 = run_graph(tmp, "lg-fanout", [fo], binary)
    rec6 = json.loads((r6 / "nodes" / "build.json").read_text())
    check("fan-out merged commit refuses a dirty lane",
          rec6["status"] == "failed" and rec6["error_class"] == "incomplete_work", rec6)
    check("fan-out refusal carries the porcelain too",
          any("tracked.txt" in l for l in rec6.get("lane_dirty", [])), rec6.get("lane_dirty"))

    # (g) the door's closed set + registered description agree on the new field
    import importlib
    spec2 = importlib.util.spec_from_file_location("door_lane", ROOT / "__init__.py")
    door = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(door)
    desc = door.WORKFLOW_PARAMS["properties"]["graph"]["description"]
    check("door description documents repo", "repo (optional path" in desc)
    import wfcommon
    check("`repo` is a validated agent key", "repo" in wfcommon.AGENT_KEYS)

    # (h) deep review #29 F3: a mistyped `repo` must FAIL validation — never
    # silently read as no-declaration and commit done over a dirty lane.
    import wfcommon as _wc
    def _v(node_extra):
        n = {"id": "v", "type": "agent", "goal": "g"}
        n.update(node_extra)
        return [e for e in _wc.validate_graph_errors([n]) if e.get("field") == "repo"]
    check("repo: 123 rejected", bool(_v({"repo": 123})))
    check('repo: ["x"] rejected', bool(_v({"repo": ["x"]})))
    check('repo: {"a":1} rejected', bool(_v({"repo": {"a": 1}})))
    check('repo: "" rejected', bool(_v({"repo": ""})))
    check('repo: " x " rejected (whitespace)', bool(_v({"repo": " x "})))
    check("repo: 'work/clone' accepted (no repo error)", not _v({"repo": "work/clone"}))


print("FAILURES" if FAILS else "ALL PASS")
sys.exit(1 if FAILS else 0)