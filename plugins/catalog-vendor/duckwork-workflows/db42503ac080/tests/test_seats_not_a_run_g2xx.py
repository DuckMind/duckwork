#!/usr/bin/env python3
"""est-g2xx follow-up — the global seat-ticket dir <runs_root>/.seats is NEVER a run.

The seat semaphore (test_seat_live_g2xx.py) keeps its tickets under
<runs_root>/.seats. Every runs-root enumeration — the door's `list`, the
dashboard read model, the card-enforcement outstanding scan — must skip it (and
any other dot-dir) by construction, through ONE shared helper
(wfcommon.iter_run_dirs), not by the accident that .seats happens to lack a
graph.json today. The adversarial case below plants a graph.json INSIDE .seats:
a name-blind enumeration would list it as a run.

est-g255 P255-6 (zap): the enumeration of the dashboard and the card scan is
asserted BEHAVIOURALLY (each read model is driven against the same adversarial
fixture and its own answer is inspected) — no test reads product source text or
pins helper spelling (CONTRIBUTING R6). The helper contract stays pinned
directly against wfcommon.iter_run_dirs (that IS the helper's behaviour), and
the adversarial planted-run door test is kept verbatim in spirit.

Run: PYTHONPATH=/opt/duckwork python3 tests/test_seats_not_a_run_g2xx.py
"""
import importlib.util, json, os, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-seats-not-run"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
RUNS = HOME / "workflows"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(HERE / "fake")
(HOME / "config.yaml").write_text("model:\n  default: seat-default\n")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

NODE = {"id": "a", "type": "agent", "goal": "x", "max_turns": 1}
GRAPH = {"name": "s", "nodes": [NODE]}
NOW_ISO = datetime.now(timezone.utc).isoformat(timespec="seconds")

# one real-shaped run + an adversarial .seats dir that LOOKS like a run —
# including a launch-shaped run.json OWNED by the card scan's probe session, so
# a name-blind enumeration would not merely list it, it would surface a phantom
# card obligation and a phantom dashboard run.
run = RUNS / "20261006-000000-s"
(run / "nodes").mkdir(parents=True)
(run / "graph.json").write_text(json.dumps(GRAPH))
(run / "run.json").write_text(json.dumps({"run_id": run.name, "name": "s",
                                           "started": NOW_ISO}))
(run / "nodes" / "a.json").write_text(json.dumps(
    {"status": "done", "output": {"answer": "ok"}, "efp": "", "ms": 1}))
seats = RUNS / ".seats"
seats.mkdir()
(seats / "123.json").write_text(json.dumps({"pid": 1}))
(seats / "graph.json").write_text(json.dumps(GRAPH))          # adversarial
(seats / "run.json").write_text(json.dumps(
    {"run_id": ".seats", "name": "s", "started": NOW_ISO,
     "owner": {"session_id": "sess-p255-6"}}))
(RUNS / "stray.txt").write_text("not a dir")

# (1) the shared helper
have = hasattr(wfcommon, "iter_run_dirs")
check("wfcommon exposes iter_run_dirs", have)
if have:
    got = [p.name for p in wfcommon.iter_run_dirs(RUNS)]
    check("iter_run_dirs yields the run, skips .seats and non-dirs", got == [run.name], got)
    check("iter_run_dirs on a missing root is empty", list(wfcommon.iter_run_dirs(HOME / "nope")) == [])

# (2) door `list` never shows .seats
door = load("door_seats", "__init__.py")
import wf_test_isolation as _iso; _iso.install(door)
lst = json.loads(door.handle({"action": "list"}))
ids = [r.get("run_id") for r in lst.get("runs", [])]
check("door list omits .seats", ".seats" not in ids, ids)
check("door list still shows the real run", run.name in ids, ids)

# (3) dashboard read model, BEHAVIOURALLY: _list_runs() against the SAME
# adversarial root must answer with the real run only — a regressed
# enumeration (raw iterdir) would project .seats as a run view.
dash = load("dash_p255_6", "dashboard/plugin_api.py")
dl = dash._list_runs()
dids = [v.get("id") for v in dl.get("runs", [])]
check("dashboard _list_runs omits the adversarial .seats run", ".seats" not in dids, dids)
check("dashboard _list_runs keeps the real run", run.name in dids, dids)

# (4) card enforcement outstanding scan, BEHAVIOURALLY: probe with the session
# that OWNS the planted .seats/run.json — a name-blind enumeration would raise
# a phantom card obligation for .seats. The real run is owned by nobody, so a
# correct scan answers with NOTHING.
card = load("card_p255_6", "card_enforcement.py")
card.bind(wfcommon, lambda r: "::workflow{id=\"%s\"}" % r.name)
hits = card._outstanding("sess-p255-6", datetime.now(timezone.utc))
hit_ids = [rid for rid, _ in hits]
check("card _outstanding omits the adversarial .seats run", ".seats" not in hit_ids, hit_ids)

shutil.rmtree(HOME, ignore_errors=True)
print("ALL PASS" if ok else "SOME FAIL")
raise SystemExit(0 if ok else 1)
