#!/usr/bin/env python3
"""B1 cooperative steer (feedback #13/#40) — the file protocol and cursor,
proved end-to-end with the fake child (compliance of the MODEL is a separate,
measured question, not claimed here).

Cases:
 1. LIVE child pull: a steer line that exists at spawn is baked and the
    child's own inbox call returns it; a second call in the same spawn returns
    [] (cursor advanced: exactly-once per spawn).
 2. HWM excludes post-spawn lines: steer that lands after the spawn baked is
    NOT visible to this spawn — it waits for the next spawn.
 3. A fresh spawn re-delivers every addressed line (per-spawn cursor starts 0).
 4. Done-node steer still refused (steer-truth law), no inbox line left.
 5. Status read model reports steer {queued, baked, consumed} from files only.
 6. Stranger inbox: no baked env -> honest refusal, ok=False.

Run: cd tests && /opt/duckwork/.venv/bin/python3 test_steer_live_40.py
"""
import importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
HOME = ROOT / "home-40"
RUNS = HOME / "workflows"
FAKE = str(BUILD / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL "
           ) + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def mk(run_id, inbox_lines):
    """Hand-built run dir with run.json meta pinning duckwork_bin to the fake —
    WITHOUT that meta the runner resolves the real duckwork binary and the test
    burns 120s of provider 429 backoff instead of the fake (learned the hard
    way; see test_failures_0923.py's mk())."""
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(
        {"name": run_id, "nodes": [{"id": "w", "type": "agent", "goal": "work"}]}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": FAKE, "concurrency": 1, "node_timeout": 60}))
    if inbox_lines:
        (r / "inbox.jsonl").write_text(
            "".join(json.dumps(l) + "\n" for l in inbox_lines))
    return r

def launch(r, env_extra=None):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_MODE="poll_steer",
               **(env_extra or {}))
    return subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", r.name],
                            env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

def wait_done(r, nid="w", timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = r / "nodes" / f"{nid}.json"
        if p.exists():
            try:
                d = json.loads(p.read_text())
            except Exception:
                d = {}
            if d.get("status") in ("done", "failed"):
                return d
        time.sleep(0.2)
    raise AssertionError(f"node {nid} never committed within {timeout}s")

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()

# ---- 1 & 2: live pull + cursor + HWM exclusion ------------------------------
# 'early nudge' exists BEFORE spawn (must be baked and pulled).
# The test appends 'late after bake' WHILE the child is awake (the fake holds
# FAKE_POLL_SLEEP seconds before pulling) — HWM must hide it from this spawn.
r = mk("b1-live", [{"node": "w", "text": "early nudge", "at": "t0"}])
proc = launch(r, {"FAKE_POLL_SLEEP": "3"})
deadline = time.time() + 30
late_written = False
while time.time() < deadline:
    cands = sorted((r / "steer").glob("w.a*.jsonl")) if (r / "steer").is_dir() else []
    if cands:
        try:
            recs = [json.loads(l) for l in cands[-1].read_text().splitlines() if l.strip()]
        except Exception:
            recs = []
        if any(x.get("text") == "early nudge" for x in recs):
            with open(r / "inbox.jsonl", "a") as f:
                f.write(json.dumps({"node": "w", "text": "late after bake", "at": "t1"}) + "\n")
            late_written = True
            break
    time.sleep(0.15)
check("spawn baked the pre-existing steer line", late_written)
proc.wait(timeout=120)
rec = wait_done(r)
out = rec.get("output") or {}
check("live child pulled the baked line", out.get("pulled") == ["early nudge"],
      json.dumps(out)[:200])
check("second pull in the same spawn is empty (cursor exactly-once)",
      out.get("repull") == [], json.dumps(out)[:200])
check("HWM excluded the post-spawn line from this spawn", out.get("pulled") != None
      and "late after bake" not in (out.get("pulled") or []), json.dumps(out)[:200])
_bake = sorted((r / "steer").glob("w.a*.jsonl"))[-1]
_check_lines = [json.loads(l) for l in _bake.read_text().splitlines() if l.strip()]
check("bake file holds exactly the spawn-time line, cursor fully consumed",
      [x["text"] for x in _check_lines] == ["early nudge"]
      and (_bake.with_name(_bake.name.replace(".jsonl", ".cursor"))).read_text() == "1",
      json.dumps({"bake": [x["text"] for x in _check_lines]})[:200])

# ---- 3: a fresh spawn re-delivers every addressed line ----------------------
r2 = mk("b1-fresh", [
    {"node": "w", "text": "seen by a past spawn", "at": "t0"},
    {"node": "w", "text": "never delivered", "at": "t1"}])
proc2 = launch(r2)
proc2.wait(timeout=120)
rec2 = wait_done(r2)
check("fresh spawn delivers every addressed line, in order",
      rec2.get("output", {}).get("pulled") == ["seen by a past spawn", "never delivered"],
      json.dumps(rec2.get("output"))[:200])
_bake2 = sorted((r2 / "steer").glob("w.a*.jsonl"))[-1]
_lines2 = [json.loads(l) for l in _bake2.read_text().splitlines() if l.strip()]
check("bake file holds both addressed lines for the fresh spawn",
      [x["text"] for x in _lines2] == ["seen by a past spawn", "never delivered"],
      json.dumps([x["text"] for x in _lines2])[:200])

# ---- 4: done-node steer refusal (steer-truth law intact) --------------------
_spec = importlib.util.spec_from_file_location("hw40", ROOT / "__init__.py")
door = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(door)

before = (r2 / "inbox.jsonl").read_text()
ans = door.act_steer({"run_id": r2.name, "node": "w", "text": "too late"})
check("done-node steer refused naming the state",
      ans.get("ok") is False and "done" in ans.get("error", ""), json.dumps(ans)[:200])
check("refusal leaves no inbox line", (r2 / "inbox.jsonl").read_text() == before)

# ---- 5: status read model steer {queued, baked, consumed} ------------------
(r2 / "inbox.jsonl").write_text(before + json.dumps({"node": "w", "text": "post-done", "at": "t2"}) + "\n")
st = door.act_status({"run_id": r2.name})
sm = (st.get("nodes", {}).get("w") or {}).get("steer")
check("status carries steer evidence from files only",
      sm == {"queued": 3, "baked": 2, "consumed": 2}, json.dumps(sm))

# ---- 6: stranger session cannot pull someone else's steering ----------------
os.environ.pop("DUCKWORK_WF_STEER_FILE", None)
os.environ.pop("DUCKWORK_WF_STEER_CURSOR", None)
ans = door.act_inbox({})
check("stranger inbox refused (no baked env)", ans.get("ok") is False, json.dumps(ans)[:160])

print("\n" + ("ALL PASS" if ok else "FAILURES PRESENT"))
sys.exit(0 if ok else 1)
