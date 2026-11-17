"""run dry_run:true = the amend dry_run shape on the launch path: validate + bind +
model-preflight return their verdict and NOTHING is written — no run dir, no lane
entry, no spawned runner. Before the fix the flag was silently ignored on `run`
(it fell through to _create_run), so a pre-launch lint had to gamble a real run.
Stdlib only; liveness ping stubbed; fake duckwork bin so no real launcher is needed.
"""
import importlib.util, json, os, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-rundry-", dir=HERE / "tests")
os.environ["DUCKWORK_HOME"] = str(tmp_dir.name)
# #71: DUCKWORK_HOME alone loses to the context-local home override — without the
# runs-root pin the normal-run launches land TWO dirs on the estate shelf.
os.environ["WF_RUNS_ROOT"] = str(Path(tmp_dir.name) / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(HERE / "tests" / "fake")   # the suite's fake duckwork
os.environ["WF_QUOTA_CACHE"] = str(Path(tmp_dir.name) / "quota-cache.json")  # test-seated: pings nothing
ALIASES = ("  aliases:\n    fable: anthropic/claude-fable-5.1\n    opus: anthropic/claude-opus-5-5\n"
           "    sol: openai-codex/gpt-6-sol\n")
(Path(tmp_dir.name) / "config.yaml").write_text("model:\n  default: qwen38-next\n" + ALIASES)
spec = importlib.util.spec_from_file_location("door_rd", HERE / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
door._ping_route_once = lambda p, m: {"liveness": "unknown"}   # no network

class Ctx:
    def get_config(self, k, d=None):
        return {"worker": "qwen38-next", "manager": "fable", "frontier": "sol"} if k == "models" else d
door._CTX = Ctx()

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {detail}" if detail and cond is not True else ""))
    fails += 0 if cond else 1

def call(**a):
    return json.loads(door.handle(a))

def author():
    return {"name": "run-dry-probe", "nodes": [
        {"id": "recon", "type": "agent", "goal": "r", "model": "manager"},
        {"id": "check", "type": "agent", "goal": "c", "model": "manager", "after": ["recon"]},
        {"id": "impl",  "type": "agent", "goal": "i", "model": "worker",  "after": ["check"]}]}

def run_dirs():
    root = door.runs_root()
    return sorted(p.name for p in root.iterdir() if p.is_dir()) if root.exists() else []

# --- 1. the flag is honored: preview, and NOTHING written -----------------------
home_before = run_dirs()
out = call(action="run", graph=author(), dry_run=True)
check("run dry_run returns ok+dry_run (the amend shape, not an ignored flag)",
      out.get("ok") is True and out.get("dry_run") is True, json.dumps(out)[:300])
check("run dry_run returns NO run_id (nothing launched)", "run_id" not in out, json.dumps(out)[:300])
rr = out.get("routes") or {}
check("run dry_run reports resolved models/routes for every node",
      set(out.get("models") or {}) and set(rr) == {"recon", "check", "impl"},
      json.dumps({"models": out.get("models"), "routes": sorted(rr)})[:300])
check("run dry_run touches NOTHING: no run dir created", run_dirs() == home_before, str(run_dirs()))

# --- 2. invalid graph is refused on the dry path, with nothing written -----------
bad = author(); bad["nodes"][1]["after"] = ["ghost"]
o2 = call(action="run", graph=bad, dry_run=True)
check("invalid graph still refused in dry_run (errors surface)", o2.get("error"), json.dumps(o2)[:300])
check("invalid graph + no errors key -> still touched nothing", run_dirs() == home_before, str(run_dirs()))

# --- 3. contract intact: normal run still launches exactly as before --------------
r = call(action="run", graph=author())
rid = r.get("run_id")
check("normal run (no dry_run) still launches", bool(rid), json.dumps(r)[:300])
rdir = door.runs_root() / (rid or "_none")
check("normal run writes run dir + spawns runner", (rdir / "graph.json").exists() and (rdir / "wf.pid").exists(),
      str(sorted(p.name for p in rdir.iterdir())) if rdir.exists() else "missing")
if rid:
    (rdir / "stop.request").write_text("test-teardown")
    for _ in range(40):                       # polite teardown: wait for the runner to settle
        if not door.runner_alive(rdir):
            break
        time.sleep(0.25)

# --- 4. lane dedup untouched by the dry path --------------------------------------
o3 = call(action="run", graph=author(), dry_run=True, lane_key="dry-lane")
check("dry_run with lane_key writes no lane entry (no dedupable claim)",
      o3.get("dry_run") is True and call(action="run", graph=author(), lane_key="dry-lane").get("run_id"),
      json.dumps(o3)[:200])

print(f"\n{'ALL PASS' if not fails else f'{fails} FAIL'}")
sys.exit(1 if fails else 0)
