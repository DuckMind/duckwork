#!/usr/bin/env python3
"""PR #97 R18 — the lost handoff: an owner action taken INSIDE the synchronous
wake POST must reach the next terminal boundary with NO wait/poll.

Contract (wf.py _WAKE_TEMPLATES): answer ONE gate release / apply ONE amend and
stop — "the run resumes on its own", "Do not poll or wait: the next transition —
including completion — wakes this session."

Failure mode pinned (dossier pr97-r18-council-dossier.md; rig runs
20261002-201713-p97-smoke-gate-smoke-r17 / 20261002-201949-p97-smoke-failonce-smoke;
independent review repro reproduced BOTH legs deterministically at 55eb8fee — pinned in
red.json). api_server holds the wake POST open for the whole owner turn, so the
runner is blocked inside notify() and STILL HOLDS the flock when the owner calls
release/amend. The door then takes the runner_alive branch:

  * release: answer written, respawn SKIPPED ("workflow wait to follow the next
    boundary"), the runner exits "held at g1" microseconds later — parked inert;
  * amend: restart.request left on disk OVER the exiting runner ("live runner
    hot-reloads ... call wait"), run parked "blocked by failed n1" — inert.

Fix shape (terminal handoff): the runner releases the flock + clears wf.pid
BEFORE the terminal park notify(), re-reads durable action state under that gap,
and either re-admits itself or yields to a door-spawn winner (kernel flock keeps
exactly-once admission; a late action in the recheck->release gap is caught by
the door's bounded respawn-wait). Success hints stop instructing wait/poll.

Mechanics note: the owner handler CANNOT call the door in this process — the
wake POST is served by the runner's own notify() on the runner's main thread, so
an in-process door action that has to wait for the runner deadlocks (proven with
a probe). Every owner action therefore rides a subprocess door (exactly like the
real gateway's tool call), and its parsed result lands in ACTS.json.

Scenarios (numbering pinned by the R18 handoff):
  1. gate release inside the sync wake POST -> run.done exactly once, gate.released,
     downstream step spawned exactly once, release ok, hint no wait/poll.
  2. failed-node amend inside the sync wake POST -> amended unique sentinel reaches
     run.done exactly once; restart.request NOT left on disk; no wait/poll hint.
  3. stop issued during the wake window is consumed: stop.request unlinked,
     run.stopped event, parked stopped, no wait/poll hint.
  4. action landing after the recheck-to-lock-release window admits exactly ONE
     runner: single run.done, no duplicate node.started (the door's respawn-wait
     may self-admit the exiting runner or spawn a winner — never both).
  5. control: action AFTER the POST returned uses the dead-runner respawn path
     (auto_resumed / "respawned") and reaches run.done exactly once.
  6. static pin: act_release / act_amend / act_stop success copy and the
     _create_run launch hint carry no wait/poll instruction.

RED discipline: run against a PRE-FIX detached worktree of 55eb8fee to prove the
failures; run against the fix tree to prove GREEN.
usage: python3 test_lost_handoff_sync_wake_r18.py <repo_root>
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1
        else Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

_tmp = Path(tempfile.mkdtemp(prefix="wf-r18-lost-handoff-"))
RUNS = _tmp / "workflows"
FAKE_LOG = _tmp / "fake.log"
ACTS = _tmp / "acts.json"
ACTS.write_text("[]")
FAKE_LOG.write_text("")
ENV = dict(os.environ,
           DUCKWORK_HOME=str(_tmp), WF_RUNS_ROOT=str(RUNS),
           DUCKWORK_WF_DUCKWORK_BIN=str(ROOT / "tests" / "fake"), FAKE_LOG=str(FAKE_LOG))
for _k in ("API_SERVER_KEY", "API_SERVER_HOST", "API_SERVER_PORT",
           "R18_CTRL", "R18_ACT", "R18_HOLD"):
    ENV.pop(_k, None)

POSTS = []          # wake POST bodies received (one thread each)
ACTS_LOCK = threading.Lock()


def _append_act(rec):
    with ACTS_LOCK:
        rows = json.loads(ACTS.read_text() or "[]")
        rows.append(rec)
        ACTS.write_text(json.dumps(rows))


class Owner(BaseHTTPRequestHandler):
    """The api_server shape: the POST stays open for the whole owner turn
    (stream=False). ENV is the RUNNER's environment (inherited at spawn), so
    the per-scenario knobs are read from os.environ here, not from ENV."""

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        text = body["messages"][0]["content"]
        POSTS.append(text)
        rid = text.split('run_id="', 1)[1].split('"', 1)[0]
        ctrl = os.environ.get("R18_CTRL")     # "defer" -> owner acts after the POST returned
        if ctrl == "defer":
            self.send_response(202); self.end_headers(); self.wfile.write(b"{}")
            threading.Thread(target=lambda: (time.sleep(2.0), self._owner_turn(text, rid)), daemon=True).start()
            return
        self._owner_turn(text, rid, hold=float(os.environ.get("R18_HOLD", "0")))

    def _owner_turn(self, text, rid, hold=0.0):
        # The runner blocks in notify() until this method returns; the door call
        # rides a SUBPROCESS (an in-process door call would deadlock the very
        # notify() that is serving us).
        if 'event="gate.held"' in text:
            if os.environ.get("R18_ACT") == "stop":
                args = {"action": "stop", "run_id": rid}
            else:
                args = {"action": "release", "run_id": rid, "gate_id": "g1", "answer": "approve"}
        elif 'event="run.failed"' in text:
            g = json.loads((RUNS / rid / "graph.json").read_text())
            for n in g["nodes"]:
                if n["id"] == "n1":
                    n["goal"] = "R18SENTINEL step"
            args = {"action": "amend", "run_id": rid, "graph": g}
        else:
            args = None
        if os.environ.get("R18_HOLD"):
            time.sleep(float(os.environ["R18_HOLD"]))   # hold the handoff window open
        if args is None:
            pass
        else:
            out = _door_call(args)
            with ACTS_LOCK:
                st = _door_call({"action": "status", "run_id": rid})
            _append_act({"action": args["action"], "result": out,
                         "runner_live_at_action": st.get("runner_live")})
        if hold:
            time.sleep(hold)          # finish the owner turn, then the POST returns
        try:
            self.send_response(202); self.end_headers(); self.wfile.write(b"{}")
        except Exception:
            pass

    def log_message(self, *a):
        pass


SRV = ThreadingHTTPServer(("127.0.0.1", 0), Owner)
threading.Thread(target=SRV.serve_forever, daemon=True).start()
os.environ.update(ENV, WF_WAKE_SINK_PORT=str(SRV.server_address[1]),
                  DUCKWORK_SESSION_ID="r18-owner", DUCKWORK_UI_SESSION_ID="r18-ui",
                  DUCKWORK_SESSION_PLATFORM="api_server")

# door module in THIS process: launch + read-model only (never an action — actions
# must ride the subprocess door so they can run while a wake POST is open).
_spec = importlib.util.spec_from_file_location("hw_r18_lh", ROOT / "__init__.py")
HW = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(HW)
import wf_test_isolation
wf_test_isolation.install(HW)

_DOOR_SNIPPET = f"""
import importlib.util, json, os, sys
ROOT = {str(ROOT)!r}
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
spec = importlib.util.spec_from_file_location("hw_door_child", os.path.join(ROOT, "__init__.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import wf_test_isolation; wf_test_isolation.install(m)
print(json.dumps(m.handle(json.loads(sys.argv[1]))))
"""


def _door_call(args):
    p = subprocess.run([sys.executable, "-c", _DOOR_SNIPPET, json.dumps(args)],
                       capture_output=True, text=True, env=os.environ, timeout=180)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
        # handle() speaks JSON (the tool contract); one parse, never two.
        return json.loads(out) if isinstance(out, str) else out
    except Exception:
        return {"error": f"door subprocess: rc={p.returncode} out={p.stdout[-300:]} err={p.stderr[-300:]}"}


checks, failures = 0, []


def check(label, cond, detail=""):
    global checks
    checks += 1
    if cond:
        print(f"PASS {label}")
    else:
        failures.append(label)
        print(f"FAIL {label}: {detail}")


def events(run):
    p = run / "events.jsonl"
    return [json.loads(l).get("event") for l in p.read_text().splitlines()
            if l.strip() and l.strip().startswith("{")] if p.exists() else []


def wait_for(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.2)
    return False


def parked(reason):
    return wait_for(lambda: (R / "runner_exit.json").exists()
                    and reason in (json.loads((R / "runner_exit.json").read_text()).get("reason") or ""),
                    30)


def action_rows(n=1, timeout=30):
    ok = wait_for(lambda: len(json.loads(ACTS.read_text() or "[]")) >= n, timeout)
    return ok, json.loads(ACTS.read_text() or "[]")


GATE_GRAPH = {"name": "r18-gate", "nodes": [
    {"id": "n1", "type": "agent", "goal": "S1N1 step"},
    {"id": "g1", "type": "gate", "after": ["n1"], "question": "go?",
     "options": ["approve", "reject"]},
    {"id": "n2", "type": "agent", "after": ["g1"], "goal": "S1N2 step"}]}
AMEND_GRAPH = {"name": "r18-amend", "nodes": [
    {"id": "n1", "type": "agent", "goal": "CRASHME boom"}]}

# ================= scenario 1: release inside the sync wake POST ==============
for k in ("R18_CTRL", "R18_ACT", "R18_HOLD"):
    os.environ.pop(k, None)
FAKE_LOG.write_text("")
ACTS.write_text("[]")
POSTS.clear()
out = HW.handle({"action": "run", "graph": GATE_GRAPH})
RID = json.loads(out).get("run_id"); R = RUNS / RID
check("S1 launch", bool(RID), out)
check("S1 wake for gate.held delivered to the owner turn",
      wait_for(lambda: any('event="gate.held"' in p for p in POSTS), 30), POSTS)
ok, acts = action_rows(1)
check("S1 release answered ok from the door", ok and acts and acts[-1]["result"].get("ok") is True, acts)
check("S1 release saw a live runner (flock held inside notify — the RED shape)",
      ok and acts[-1].get("runner_live_at_action") is True, acts)
done = wait_for(lambda: "run.done" in events(R), 60)
ev = events(R)
check("S1 release in-POST reaches run.done exactly once", done and ev.count("run.done") == 1, ev)
check("S1 gate.released recorded", "gate.released" in ev, ev)
check("S1 downstream spawned exactly once (no double drive)",
      FAKE_LOG.read_text().count("S1N1 step") == 1
      and FAKE_LOG.read_text().count("S1N2 step") == 1, FAKE_LOG.read_text())

# ================= scenario 2: amend inside the sync wake POST ===============
FAKE_LOG.write_text("")
ACTS.write_text("[]")
POSTS.clear()
out = HW.handle({"action": "run", "graph": AMEND_GRAPH})
RID = json.loads(out).get("run_id"); R = RUNS / RID
check("S2 wake for run.failed delivered",
      wait_for(lambda: any('event="run.failed"' in p for p in POSTS), 40), POSTS)
ok, acts = action_rows(1)
check("S2 amend accepted ok", ok and acts[-1]["result"].get("ok") is True, acts)
done = wait_for(lambda: "run.done" in events(R), 60)
ev = events(R)
check("S2 amend in-POST reaches run.done exactly once", done and ev.count("run.done") == 1, ev)
check("S2 amended unique sentinel ran exactly once",
      FAKE_LOG.read_text().count("R18SENTINEL") == 1, FAKE_LOG.read_text())
check("S2 restart.request consumed, never left on disk", not (R / "restart.request").exists(), str(R))
check("S2 exactly one drive of n1 after parking (no duplicate wave)",
      ev.count("node.started") == 2, ev)

# ================= scenario 3: stop consumed during the wake window ==========
ACTS.write_text("[]")
POSTS.clear()
os.environ["R18_ACT"] = "stop"
out = HW.handle({"action": "run", "graph": GATE_GRAPH})
RID = json.loads(out).get("run_id"); R = RUNS / RID
check("S3 wake for gate.held delivered",
      wait_for(lambda: any('event="gate.held"' in p for p in POSTS), 30), POSTS)
ok, acts = action_rows(1)
os.environ.pop("R18_ACT", None)
check("S3 stop answered ok", ok and acts[-1]["result"].get("ok") is True, acts)
stopped = wait_for(lambda: "run.stopped" in events(R), 40)
ev = events(R)
check("S3 stop consumed: run.stopped event", stopped, ev)
check("S3 stop.request unlinked (consumed, not stranded)", not (R / "stop.request").exists(), str(R))
check("S3 run ends stopped and NEVER run.done", "run.done" not in ev, ev)

# ================= scenario 5: control — action after the POST returned ======
FAKE_LOG.write_text("")
ACTS.write_text("[]")
POSTS.clear()
os.environ["R18_CTRL"] = "defer"
out = HW.handle({"action": "run", "graph": AMEND_GRAPH})
RID = json.loads(out).get("run_id"); R = RUNS / RID
ok, acts = action_rows(1, timeout=25)
os.environ.pop("R18_CTRL", None)
check("S5 delayed async amend accepted ok", ok and acts[-1]["result"].get("ok") is True, acts)
copy = json.dumps(acts[-1]["result"]).lower() if ok else ""
check("S5 continuation is automatic without wait/poll",
      ok and "call wait" not in copy and "workflow wait" not in copy and "wait to follow" not in copy,
      copy)
done = wait_for(lambda: "run.done" in events(R), 60)
ev = events(R)
check("S5 respawn reaches run.done exactly once", done and ev.count("run.done") == 1, ev)
check("S5 sentinel ran exactly once", FAKE_LOG.read_text().count("R18SENTINEL") == 1,
      FAKE_LOG.read_text())

# ===== scenario 4a: residual liveness flip respawns exactly once ===============
_real_alive, _real_respawn = HW.runner_alive, HW._respawn_runner
_seq, _spawns = iter((True, True, False)), []
setattr(HW, "runner_alive", lambda _r: next(_seq, False))
setattr(HW, "_respawn_runner", lambda _r: _spawns.append(str(_r)))
try:
    mode = HW._resume_after_action(Path("/synthetic-run"), grace_s=0.2)
finally:
    setattr(HW, "runner_alive", _real_alive)
    setattr(HW, "_respawn_runner", _real_respawn)
check("S4a residual liveness flip reports respawned", mode == "respawned", str(mode))
check("S4a residual liveness flip spawns exactly once", len(_spawns) == 1, str(_spawns))

# ===== scenario 4b: slow owner acts after WAKE_TIMEOUT/dead runner =============
# Hold the synchronous POST beyond WAKE_TIMEOUT_S (10s). The original runner
# times out and parks; the later action must use the dead-runner respawn path.
FAKE_LOG.write_text("")
ACTS.write_text("[]")
POSTS.clear()
os.environ["R18_HOLD"] = "11.5"
out = HW.handle({"action": "run", "graph": AMEND_GRAPH})
RID = json.loads(out).get("run_id"); R = RUNS / RID
check("S4b wake delivered", wait_for(lambda: any('event="run.failed"' in p for p in POSTS), 40), POSTS)
ok, acts = action_rows(1, timeout=45)
os.environ.pop("R18_HOLD", None)
check("S4b slow-owner amend accepted ok", ok and acts[-1]["result"].get("ok") is True, acts)
check("S4b slow-owner action uses respawn path",
      ok and "respawn" in json.dumps(acts[-1]["result"]).lower(), acts)
done = wait_for(lambda: "run.done" in events(R), 60)
ev = events(R)
check("S4b slow-owner handoff reaches run.done once", done and ev.count("run.done") == 1, ev)
check("S4b no duplicate admission (node.started == original + one resume)",
      ev.count("node.started") == 2, ev)
check("S4b sentinel ran exactly once", FAKE_LOG.read_text().count("R18SENTINEL") == 1,
      FAKE_LOG.read_text())

# ============ scenario 6: static pin — no wait/poll in success copy ==========
import inspect
import re
WAITY = re.compile(r"call(?:ing)? (?:workflow )?wait\b|wait to follow|resume as needed"
                   r"|to follow the next boundary|\(wait again\)|then call wait", re.I)
for name in ("act_release", "act_amend", "act_stop"):
    src = inspect.getsource(getattr(HW, name))
    # only the string literals count as agent-visible copy
    lits = " ".join(re.findall(r'"(?:[^"\\]|\\.)*"', src))
    check(f"S6 {name} success copy carries no wait/poll instruction",
          not WAITY.search(lits), lits[:400])
# _create_run: the PASTE line keeps its own word (pinned verbatim by
# test_preflight_liveness_152be7f7 PASTE); everything else must stay clean.
src = inspect.getsource(HW._create_run)
lits = " ".join(re.split(r"PASTE", src)[1:]) if "PASTE" in src else src
lits = " ".join(re.findall(r'"(?:[^"\\]|\\.)*"', lits))
check("S6 _create_run hint copy carries no wait/poll instruction",
      not WAITY.search(lits), lits[:400])

print(f"\n{'ALL PASS' if not failures else str(len(failures)) + ' FAIL'} — "
      f"{checks} checks, failures: {failures}")
print(f"workspace kept at {_tmp}")
sys.exit(1 if failures else 0)
