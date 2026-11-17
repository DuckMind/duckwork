#!/usr/bin/env python3
"""est-g255 r2 R3 (zap CHANGES at 1233d3fd, MED) — EVERY step after a
successful Popen, INCLUDING the meta['_procs'] registry insertion and the
heartbeat-path setup, must sit inside the one cleanup owner: a fault there
leaves NO orphan child and NO retained ticket.

Failure (zap r2 probes-repo.json / registration-runtime + registration-oserror +
heartbeat-setup): fault-injecting at the post-Popen registry insert or the
heartbeat-sidecar setup escaped the kill/reap/release owner with a live
immediate child AND a held seat ticket (the immediate-child gap also reproduces
at the matched base; the PERSISTENT ticket retention is PR-added relative to
that base — the fix must remove the leak the PR introduced and pull both
seams under the same boundary).

Fix contract (wf.py): once Popen succeeds, any exception at registration,
heartbeat setup, or any later setup step kills + reaps the immediate child,
unregisters, releases the seat ticket, closes the log fd — then surfaces the
fault (the typed launcher-spawn return is preserved ONLY for a Popen that
never happened).

Proof of Popen per case: the injected registry seam observes the Popen object
the product tries to register (its pid), so the control provably reached the
post-Popen side even when the child is killed before it writes any FAKE_LOG
line.

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_postpopen_cleanup_r2_g255.py
"""
import importlib.util, json, os, shutil, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-r2-clean"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
RUNS = HOME / "workflows"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)
for k in ("WF_SEATS_DIR", "WORKFLOW_MAX_SEATS", "WF_TEST_BUILD", "FAKE_LOG"):
    os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location("hw_r2_clean", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " ) + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

class Boom(RuntimeError):
    pass

class SpyRegistry(dict):
    """Records every registration insert; raises once on the rg:-keyed insert
    when boom is set (the inserted value IS the Popen object — proof Popen
    returned, even when the child dies before writing any FAKE_LOG line)."""
    def __init__(self, *a, boom=None, **k):
        super().__init__(*a, **k)
        self.seen = []          # [(key, pid)] of every registration ATTEMPT
        self.boom = boom        # exception class or None
        self.fired = False
    def __setitem__(self, k, v):
        pid = getattr(v, "pid", None)
        if pid is not None:
            self.seen.append((str(k), pid))
        if self.boom is not None and not self.fired and str(k).startswith("rg:"):
            self.fired = True
            raise self.boom("injected registry fault")
        super().__setitem__(k, v)

def fresh_meta(run_id, procs=None):
    run = RUNS / run_id
    (run / "nodes").mkdir(parents=True)
    node = {"id": "rg", "type": "agent", "goal": "ok"}
    (run / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [node]}))
    return run, node, {"_run": run, "duckwork_bin": str(HERE / "fake"),
                       "_spawn_n": {}, "_procs_lock": threading.Lock(),
                       "_procs": procs if procs is not None else {},
                       "_stop": threading.Event(), "node_timeout": 30}

def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return not state.startswith("Z")
    except (OSError, IndexError):
        return True

def stray_children():
    ps = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                        text=True).stdout
    return [l for l in ps.splitlines() if "fake_duckwork.py" in l and str(HOME) in l]

def leaked_tickets():
    return [p.name for p in seats.glob("*.json")] if seats.exists() else []

seats = HOME / "seats"

# ---------- (A) RuntimeError BETWEEN Popen and the registry write completing.
os.environ["WF_SEATS_DIR"] = str(seats)
os.environ["FAKE_LOG"] = str(HOME / "fakeA.log"); (HOME / "fakeA.log").write_text("")
reg = SpyRegistry(boom=Boom)
run, node, meta = fresh_meta("r2-clean-a", procs=reg)
raised = None
try:
    wf.run_child(meta, node, {"rg": node}, "ok", "", None, skey="wf:r:rg")
except BaseException as e:
    raised = e
time.sleep(0.3)
child_pids = [pid for _, pid in reg.seen]
check("A: the control reached the post-Popen seam (the product handed the "
      "registry a live Popen object before the fault)",
      reg.fired and bool(child_pids), f"registry never saw a Popen: {reg.seen}")
check("A: the injected registry fault propagates (no silent swallow)",
      isinstance(raised, Boom), repr(raised))
check("A: no orphan child survives the registry-insert fault",
      all(not pid_alive(p) for p in child_pids) and stray_children() == [],
      f"survivors={[p for p in child_pids if pid_alive(p)]} stray={stray_children()}")
check("A: no ticket retained after the registry-insert fault (PR-added leak)",
      leaked_tickets() == [], f"leaked: {leaked_tickets()}")
check("A: the child never stays registered in meta['_procs']",
      not list(reg.keys()), f"still registered: {list(reg.keys())}")

# ---------- (B) RuntimeError at the heartbeat-path setup, AFTER registration.
os.environ["FAKE_LOG"] = str(HOME / "fakeB.log"); (HOME / "fakeB.log").write_text("")
reg_b = SpyRegistry()          # registration succeeds; heartbeat setup faults
run, node, meta = fresh_meta("r2-clean-b", procs=reg_b)
real_hb = wf._heartbeat_path
def _boom_hb(lp):
    raise Boom("injected heartbeat-setup fault")
wf._heartbeat_path = _boom_hb
raised_b = None
try:
    wf.run_child(meta, node, {"rg": node}, "ok", "", None, skey="wf:r:rg")
except BaseException as e:
    raised_b = e
finally:
    wf._heartbeat_path = real_hb
time.sleep(0.3)
child_pids_b = [pid for _, pid in reg_b.seen]
check("B: the control reached the post-Popen + post-registration seam",
      bool(child_pids_b), f"registry never saw a Popen: {reg_b.seen}")
check("B: the injected heartbeat-setup fault propagates",
      isinstance(raised_b, Boom), repr(raised_b))
check("B: no orphan child survives the heartbeat-setup fault",
      all(not pid_alive(p) for p in child_pids_b) and stray_children() == [],
      f"survivors={[p for p in child_pids_b if pid_alive(p)]} stray={stray_children()}")
check("B: no ticket retained after the heartbeat-setup fault",
      leaked_tickets() == [], f"leaked: {leaked_tickets()}")
check("B: deregistered from meta['_procs']", not list(reg_b.keys()),
      f"still registered: {list(reg_b.keys())}")

# ---------- (C) OSError at the registry insert AFTER a successful Popen must
# not escape as the typed launcher-spawn return with a live child + ticket.
os.environ["FAKE_LOG"] = str(HOME / "fakeC.log"); (HOME / "fakeC.log").write_text("")
reg_c = SpyRegistry(boom=OSError)
run, node, meta = fresh_meta("r2-clean-c", procs=reg_c)
res_c, raised_c = None, None
try:
    res_c = wf.run_child(meta, node, {"rg": node}, "ok", "", None, skey="wf:r:rg")
except BaseException as e:
    raised_c = e
time.sleep(0.3)
child_pids_c = [pid for _, pid in reg_c.seen]
check("C: the control reached the post-Popen seam (OSError variant)",
      reg_c.fired and bool(child_pids_c), f"registry never saw a Popen: {reg_c.seen}")
check("C: registry OSError after Popen leaves NO orphan child",
      all(not pid_alive(p) for p in child_pids_c) and stray_children() == [],
      f"survivors={[p for p in child_pids_c if pid_alive(p)]}")
check("C: registry OSError after Popen leaves NO retained ticket",
      leaked_tickets() == [], f"leaked: {leaked_tickets()}")
check("C: the failure is surfaced (re-raise OR typed failed return), never "
      "swallowed as success",
      isinstance(raised_c, OSError) or (res_c or {}).get("status") == "failed",
      json.dumps(res_c, default=str)[:200])

# ---------- (D) CONTROL: no fault — the clean spawn runs, the FAKE_LOG line
# appears, and the ticket is released by the reap.
os.environ["FAKE_LOG"] = str(HOME / "fakeD.log"); (HOME / "fakeD.log").write_text("")
run, node, meta = fresh_meta("r2-clean-d")
res_d = wf.run_child(meta, node, {"rg": node}, "ok", "", None, skey="wf:r:rg")
check("D: the clean path still spawns and reports done",
      res_d.get("status") == "done" and
      len((HOME / "fakeD.log").read_text().splitlines()) == 1,
      json.dumps({k: res_d.get(k) for k in ("status", "error_class", "error")})[:200])
check("D: the clean path releases its ticket",
      leaked_tickets() == [], f"leaked: {leaked_tickets()}")

# ---------- (E) launcher-failure shape preserved: a Popen that never returns
# still yields the typed error_class=spawn return (R3 must not launder it).
os.environ["FAKE_LOG"] = str(HOME / "fakeE.log"); (HOME / "fakeE.log").write_text("")
run, node, meta = fresh_meta("r2-clean-e")
real_popen = wf.subprocess.Popen
class DeadPopen:
    def __init__(self, *a, **k):
        raise OSError(2, "simulated launcher failure")
wf.subprocess.Popen = DeadPopen
try:
    res_e = wf.run_child(meta, node, {"rg": node}, "ok", "", None, skey="wf:r:rg")
finally:
    wf.subprocess.Popen = real_popen
check("E: a launcher that never launches keeps the typed spawn return",
      res_e.get("error_class") == "spawn",
      json.dumps({k: res_e.get(k) for k in ("status", "error_class", "error")})[:200])
check("E: a failed launcher releases its seat (no ticket retained)",
      leaked_tickets() == [], f"leaked: {leaked_tickets()}")

for k in ("WF_SEATS_DIR", "FAKE_LOG"):
    os.environ.pop(k, None)
shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
