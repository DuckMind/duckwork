#!/usr/bin/env python3
"""est-bbfy: pre-cap persist/finish budget cue (residual half of est-2ek.1.95).

When an agent lane with a turn cap nears its max_turns, the runner gives it ONE
deterministic chance to persist work and prepare its final answer BEFORE the
hard cap kills it. Shape (ponytail: smallest):

  While the spawn is live the runner reads its api_call_count through the SAME
  state.db join that already proves liveness (wfcommon.child_metrics). Once the
  consumed turns reach `max_turns - margin` (margin from run.json meta
  `budget_cue_margin`, default 5 — the door's channel, same law as
  _retry_conf_params), the runner drops ONE steer line into the run's
  inbox.jsonl — the exact steer.baked channel act_steer uses — reading:
  'turn budget: N turns left — persist your work now (commit/push per
  checkpoint law) and prepare your final fenced-json answer'.

  Idempotence: a marker file under <run>/budget_cue/<node> is the claim — one
  cue per (node,index) for the life of the RUN, surviving respawn/re-drive.
  Zero behavior change under the cap: no cap, unknown counter, or turns still
  above the soft-cap => no file, no line, no event (honest absence).

  stop_reason kind: when the lane STILL dies at the hard cap after the cue was
  injected, the door's structured stop_reason (#199) gains kind='budget' — a
  runner-authored deterministic fact (the marker file), never prose.

Engine-driven with the fake duckwork (FAKE_MODE=budget_lane / typed_maxturns),
mirroring tests/test_stop_reason_status_95.py's harness shape.
"""
import importlib.util
import json, os, shutil, subprocess, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
sys.path.insert(0, str(ROOT))
HOME = BUILD / "home_bbfy"
os.environ["DUCKWORK_HOME"] = str(HOME)  # door's run_dir()/act_status() resolve home in-process
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
RUNS = HOME / "workflows"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake_bbfy.log"))
FAKE = str(BUILD / "fake")

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

def mk(run_id, nodes, extra=None):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    cfg = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 60}
    cfg.update(extra or {})
    (r / "run.json").write_text(json.dumps(cfg))
    return r

def wf(run_id, extra_env=None):
    e = dict(env)
    for k in ("FAKE_API_CALLS", "FAKE_ATTEMPT_DIR", "FAKE_BUDGET_STOP_AT", "FAKE_BUDGET_TICK"):
        e.pop(k, None)
    e.update(extra_env or {})
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                       env=e, capture_output=True, text=True, timeout=180)
    return p.stdout.strip()

def load_door():
    spec = importlib.util.spec_from_file_location("budget_cue_door", ROOT / "__init__.py")
    door = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(door)
    return door

def cue_rows(r):
    p = r / "inbox.jsonl"
    if not p.exists():
        return []
    out = []
    for l in p.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        try:
            m = json.loads(l)
        except Exception:
            continue
        if m.get("budget_cue"):
            out.append(m)
    return out

def events(r):
    p = r / "events.jsonl"
    if not p.exists():
        return []
    out = []
    for l in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(BUILD / "fake_bbfy.log").write_text("")

door = load_door()

# ---- (1) cue injected exactly once at the soft-cap, on the steer channel ----
# (3) stays exactly one across the runner's respawn/re-drive (idempotence)  ----
CAP = 30
r = mk("bbfy-lane", [{"id": "a", "type": "agent", "goal": "bbfy lane budget", "max_turns": CAP}])
wf("bbfy-lane", {"FAKE_MODE": "budget_lane", "FAKE_BUDGET_TICK": "0.25"})

rows = cue_rows(r)
check("(1) exactly ONE budget cue line was injected", len(rows) == 1,
      f"got {len(rows)}: {json.dumps(rows)[:300]}")
if rows:
    t = rows[0].get("text", "")
    n = t.split(" ")[2] if t.startswith("turn budget: ") else "?"
    check("(1) cue names the remaining turns", n.isdigit() and 0 <= int(n) <= 5, t[:120])
    check("(1) cue tells the lane to persist work now", "persist your work now" in t, t[:120])
    check("(1) cue tells the lane to prepare its final fenced-json answer",
          "prepare your final fenced-json answer" in t, t[:120])
    check("(1) cue addressed to the lane's node", rows[0].get("node") == "a", json.dumps(rows[0])[:200])
evs = [e for e in events(r) if e.get("event") == "budget_cue.injected"]
check("(1) the injection is an event fact in events.jsonl", len(evs) >= 1,
      json.dumps([e.get("event") for e in events(r)])[:300])
check("(1) marker file claimed in the run dir", (r / "budget_cue" / "a").exists(),
      str(sorted(p.name for p in (r / "budget_cue").iterdir())) if (r / "budget_cue").is_dir() else "no dir")

# the hard-cap death re-drove the node (bounded retry): >=2 spawns recorded...
starts = [e for e in events(r) if e.get("event") in ("node.started", "node.retry")
          and e.get("node") == "a"]
check("(3) the runner really respawned/re-drove the lane", len(starts) >= 2,
      f"starts: {len(starts)}")
# the LIVE spawn (a0) can pull the cue at its next inbox seam: drive the door's
# own child-side reader against a copy of a0's cursor (hwm was 0 at a0's bake).
bake0, cur0 = r / "steer" / "a.a0.jsonl", r / "steer" / "a.a0.cursor"
pulled = []
if bake0.is_file() and cur0.is_file():
    tcur = r / "steer" / "a.a0.cursor.probe"
    shutil.copy(cur0, tcur)
    pulled, _n = door._steer_lines(str(bake0), str(tcur), 0)
    tcur.unlink()
check("(1) the live spawn pulls the cue via its inbox seam (door._steer_lines)",
      len(pulled) == 1 and "persist your work now" in pulled[0], json.dumps(pulled)[:200])
bake2 = r / "steer" / "a.a1.jsonl"
check("(3) the cue rides the worker's next spawn seam via the steer.baked channel",
      bake2.is_file() and "persist your work now" in bake2.read_text(encoding="utf-8"),
      str(bake2) + (" (missing)" if not bake2.is_file() else ""))
check("(3) idempotence: STILL exactly one cue after the respawn", len(cue_rows(r)) == 1,
      f"got {len(cue_rows(r))}")

rec = json.loads((r / "nodes" / "a.json").read_text())
check("(4) the lane really died at the hard cap", rec.get("status") == "failed"
      and rec.get("error_class") == "cap_exhausted", json.dumps(rec)[:220])
st = door.act_status({"run_id": "bbfy-lane"})
sr = st.get("stop_reason")
check("(4) stop_reason present with class=cap_exhausted",
      isinstance(sr, dict) and sr.get("class") == "cap_exhausted", json.dumps(st)[:240])
check("(4) stop_reason.kind == budget (cue-then-cap death, runner-authored fact)",
      isinstance(sr, dict) and sr.get("kind") == "budget", json.dumps(sr))

# ---- (2) no injection while the lane stays above the soft-cap ----
r = mk("bbfy-early", [{"id": "b", "type": "agent", "goal": "bbfy early finish", "max_turns": CAP}])
wf("bbfy-early", {"FAKE_MODE": "budget_lane", "FAKE_BUDGET_TICK": "0.25",
                  "FAKE_BUDGET_STOP_AT": str(CAP - 10)})   # answers cleanly at 20 of 30
rec = json.loads((r / "nodes" / "b.json").read_text())
check("(2) the early lane really succeeded", rec.get("status") == "done", str(rec.get("status")))
check("(2) NO cue injected under the soft-cap", cue_rows(r) == [], json.dumps(cue_rows(r))[:200])
check("(2) NO marker dir (zero behavior change)", not (r / "budget_cue").exists(),
      str(r / "budget_cue"))
st = door.act_status({"run_id": "bbfy-early"})
check("(2) honest absence: no stop_reason on the healthy run", "stop_reason" not in st,
      json.dumps(st)[:220])

# ---- (2b) cap death WITHOUT a cue: class rides, kind stays absent ----
r = mk("bbfy-nocue", [{"id": "c", "type": "agent", "goal": "bbfy nocue typed", "max_turns": CAP}])
wf("bbfy-nocue", {"FAKE_MODE": "typed_maxturns"})   # dies instantly, counter never seen
rec = json.loads((r / "nodes" / "c.json").read_text())
check("(2b) cap death recorded without any counter evidence",
      rec.get("status") == "failed" and rec.get("error_class") == "cap_exhausted",
      json.dumps(rec)[:200])
st = door.act_status({"run_id": "bbfy-nocue"})
sr = st.get("stop_reason")
check("(2b) class present, kind ABSENT (no cue = never claim budget)",
      isinstance(sr, dict) and sr.get("class") == "cap_exhausted" and "kind" not in sr,
      json.dumps(sr))

# ---- (5) the knob: run.json meta budget_cue_margin is honoured (door's channel) ----
r = mk("bbfy-knob", [{"id": "d", "type": "agent", "goal": "bbfy knob margin", "max_turns": CAP}],
       extra={"budget_cue_margin": 2})
wf("bbfy-knob", {"FAKE_MODE": "budget_lane", "FAKE_BUDGET_TICK": "0.25",
                 "FAKE_BUDGET_STOP_AT": str(CAP - 4)})     # answers at 26: inside margin 5, outside margin 2
rec = json.loads((r / "nodes" / "d.json").read_text())
check("(5) knob lane succeeded on its own", rec.get("status") == "done", str(rec.get("status")))
check("(5) margin=2 means NO cue at 4 turns left", cue_rows(r) == [], json.dumps(cue_rows(r))[:200])

print(("PASS" if fails == 0 else "FAIL") + f" test_budget_cue_bbfy ({fails} failing checks)")
sys.exit(0 if fails == 0 else 1)
