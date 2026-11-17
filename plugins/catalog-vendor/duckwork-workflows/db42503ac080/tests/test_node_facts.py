"""O2 backend acceptance (L4): wfcommon.node_facts, the /runs/{id}/nodes/{nid}/log
route, the partial-output read fix, the _steer_state move (door keeps its alias).

Against a fake-child run dir (records hand-written the way wf.py commits them).
Stdlib-only + the plugin's own imports; the route core is exercised directly so
the gate does not depend on a test HTTP client."""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import asyncio, importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon

def _load_iso762():
    # est-2ek.1.762: shared launch-env pin helper, exec-loaded by file path
    # (repo convention — a top-level import of a tests/fixtures module would
    # break the test_packaging import-closure from the unpacked package root).
    spec = importlib.util.spec_from_file_location(
        "wf_spawn_isolation_762", Path(__file__).parent / "fixtures" / "wf_spawn_isolation_762.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
pin_env = _load_iso762().pin_env

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

HOME = Path(tempfile.mkdtemp(prefix="home-node-facts-", dir=str(ROOT)))
os.environ["DUCKWORK_HOME"] = str(HOME)
# est-2ek.1.762: the route/dashboard resolvers honor WF_RUNS_ROOT above
# DUCKWORK_HOME — a test that reads <home>/workflows must pin the ONE resolver
# to that dir or a hostile/suite-exported root makes every run "unknown".
os.environ.update(pin_env({}, HOME / "workflows", home=HOME))
api = load("node_facts_dashboard", ROOT / "dashboard" / "plugin_api.py")
door = load("node_facts_door", ROOT / "__init__.py")

ok = 0
def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1; print("PASS", msg)

def call(route_fn, **kw):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(route_fn(**kw))

def route_for(path):
    for rt in api.router.routes:
        if getattr(rt, "path", None) == path:
            return rt.endpoint
    raise AssertionError(f"route {path} not registered")

get_log = route_for("/runs/{run_id}/nodes/{nid}/log")
get_run = route_for("/runs/{run_id}")

# ---------- fake-child run dir ----------
RUN = "nf-run"
r = HOME / "workflows" / RUN
(r / "nodes").mkdir(parents=True)
(r / "logs").mkdir()
(r / "gates").mkdir()
graph = {"name": "node-facts", "nodes": [
    {"id": "solo", "type": "agent", "goal": "do it"},
    {"id": "part", "type": "agent", "goal": "die after json", "after": ["solo"]},
    {"id": "run", "type": "agent", "goal": "still going", "after": ["solo"]},
    {"id": "wait", "type": "agent", "goal": "not spawned", "after": ["part"]}]}
byid = {n["id"]: n for n in graph["nodes"]}
(r / "graph.json").write_text(json.dumps(graph))
(r / "run.json").write_text(json.dumps({"name": "node-facts", "duckwork_bin": "/bin/true"}))

def rec(nid, **kw):
    (r / "nodes" / f"{nid}.json").write_text(json.dumps({**kw, "fp_rule_version": wfcommon.FP_RULE_VERSION}))

rec("solo", status="done", output={"result": "fine"}, ms=120, efp=wfcommon.efp(byid, byid["solo"]),
    skey="wf:nf-run:solo:abcd1234.000001", attempts=1, attempts_log=[], final="",
    harvest=None, error=None, error_class=None, started="2026-01-01T00:00:00+00:00",
    log_path=str(r / "logs" / "solo.a0.log"), prompt_path=str(r / "logs" / "solo.a0.prompt.md"))
rec("part", status="partial", output={"result": "harvested"}, error="child died, answer harvested",
    error_class="timeout", harvest={"declared_status": None}, ms=900, attempts=1,
    attempts_log=[{"attempt": 0, "error_class": "timeout"}], final="I got most of the way",
    efp=wfcommon.efp(byid, byid["part"]), started="2026-01-01T00:10:00+00:00",
    log_path=str(r / "logs" / "part.a0.log"))
rec("run", status="running", spawn_cmd=["duckwork", "chat"], log_path=str(r / "logs" / "run.a0.log"),
    pid=0, started="2026-01-01T00:20:00+00:00", skey="wf:nf-run:run:beef0000.000002",
    attempt=0, efp=wfcommon.efp(byid, byid["run"]))

big = bytes((i * 7 + 3) % 251 + 1 for i in range(40000))  # deterministic 40 KB, no zeros
(r / "logs" / "solo.a0.log").write_bytes(big)
(r / "logs" / "solo.a0.prompt.md").write_text("# prompt\n## Inputs\nparent output here\n")
(r / "logs" / "part.a0.log").write_bytes(b"tail-me-" + b"x" * 500)
(r / "logs" / "run.a0.log").write_bytes(b"live child output\n")

# steer evidence for `part`: 2 queued to it, 2 baked, cursor=1 consumed (+1 kill cmd ignored)
(r / "inbox.jsonl").write_text("\n".join([
    json.dumps({"node": "part", "text": "keep going"}),
    json.dumps({"node": "part", "text": "also this"}),
    json.dumps({"node": "part", "cmd": "kill"}),
    json.dumps({"node": "other", "text": "not yours"})]) + "\n")
(r / "steer").mkdir()
(r / "steer" / "part.a0.jsonl").write_text(
    json.dumps({"text": "keep going"}) + "\n" + json.dumps({"text": "also this"}) + "\n")
(r / "steer" / "part.a0.cursor").write_text("1")

# ---------- 1) /runs/{id} node keys equal the record's keys, or read `unknown` ----------
view = api._view(r, full=True)
nodes = view["nodes"]
for nid, want_rec in (("solo", True), ("part", True), ("run", True), ("wait", False)):
    nv = nodes[nid]
    if not want_rec:
        continue
    disk = json.loads((r / "nodes" / f"{nid}.json").read_text())
    missing = [k for k in wfcommon.FACT_KEYS if k != "status" and k not in nv]
    check(not missing, f"{nid}: every fact key present in the view ({missing})")
    wrong = [k for k in wfcommon.FACT_KEYS if k != "status"
             and nv[k] != (disk[k] if k in disk and disk[k] is not None else "unknown")]
    check(not wrong, f"{nid}: every fact verbatim from the record or 'unknown' ({wrong})")
# a record WITHOUT most keys still reads `unknown`, never fabricates 0/None
rec("bare", status="done")  # a record carrying ONLY status: every other fact must read `unknown`
bf = wfcommon.node_facts(r, "bare")
check(all(bf[k] == "unknown" for k in wfcommon.FACT_KEYS if k != "status"),
    "node_facts: absent record fields read 'unknown', never fabricated")
check(wfcommon.node_facts(r, "no-such-node") is None, "node_facts: no record at all = None (never fabricated)")

# ---------- 2) a partial node's output is non-null (the live drop bug) ----------
check(nodes["part"]["status"] == "partial", "partial node keeps its derived status")
check(nodes["part"]["output"] == {"result": "harvested"}, "partial node's output ships non-null")
check(nodes["part"]["harvest"] == {"declared_status": None}, "partial node carries harvest verbatim")
check(nodes["run"]["log_path"] == str(r / "logs" / "run.a0.log") and nodes["run"]["skey"]
      == "wf:nf-run:run:beef0000.000002", "running node exposes spawn-time log_path/started/skey")
check("question" not in nodes["solo"] and "options" not in nodes["solo"],
      "placeholder question/options/goal triple is gone from the projection")

# steer truth rides node_facts (and the door's _steer_state move)
check(nodes["part"]["steer"] == {"queued": 2, "baked": 2, "consumed": 1},
      "node_facts carries steer queued/baked/consumed from files only")
check(door._steer_state is door._common._steer_state, "door keeps the _steer_state alias after the move")
st = door.act_status({"run_id": RUN})
check(st["nodes"]["part"].get("steer") == {"queued": 2, "baked": 2, "consumed": 1},
      "act_status still resolves steer through the door alias")

# ---------- 3) the log route returns the file's LAST N bytes ----------
res = call(get_log, run_id=RUN, nid="solo", index=None, attempt=None, kind="log", tail=1024)
check(isinstance(res, dict) and "content" in res, "log route answered with a content field")
check(res["content"] == big[-1024:].decode("utf-8", errors="replace"), "log tail returns the last N bytes")
check(res["size"] == len(big) and res["bytes"] == 1024, "route reports size + returned bytes")
res = call(get_log, run_id=RUN, nid="solo", index=None, attempt=None, kind="prompt", tail=16384)
check("## Inputs" in res["content"], "prompt kind serves the record's prompt_path")
res = call(get_log, run_id=RUN, nid="part", index=None, attempt=None, kind="log", tail=8)
check(res["content"] == "x" * 8, "small tail honored")

# ---------- 4) crafted ids / escape attempts = 404 ----------
from fastapi import HTTPException
def expect404(fn, *a, **kw):
    try:
        call(fn, *a, **kw)
    except HTTPException as e:
        return e.status_code == 404
    return False

check(expect404(get_log, run_id=RUN, nid="../solo", index=None, attempt=None, kind="log", tail=16),
      "crafted nid escaping the record = 404")
check(expect404(get_log, run_id=RUN, nid="..%2Fsolo", index=None, attempt=None, kind="log", tail=16),
      "url-encoded escape nid = 404 (ID_OK)")
check(expect404(get_log, run_id=RUN, nid="solo", index=None, attempt=-1, kind="log", tail=16),
      "negative attempt = 404")
check(api._node_log_tail(r, "solo", None, "../../etc/pa", "log", 16) is None,
      "crafted attempt string that could escape = 404 at the core")
# a record that LIES about its path must still be contained
rec("liar", status="done", log_path="/etc/passwd", prompt_path=str(r / ".." / ".." / "outside.md"))
check(api._node_log_tail(r, "liar", None, None, "log", 16) is None,
      "record log_path outside <run>/logs = 404 (containment)")
check(api._node_log_tail(r, "liar", None, None, "prompt", 16) is None,
      "record prompt_path escaping <run>/logs = 404 (containment)")
check(expect404(get_log, run_id=RUN, nid="ghost", index=None, attempt=None, kind="log", tail=16),
      "no record = 404")
check(expect404(get_log, run_id="no-such-run", nid="solo", index=None, attempt=None, kind="log", tail=16),
      "unknown run = 404")
check(expect404(get_log, run_id=RUN, nid="solo", index=None, attempt=None, kind="kind", tail=16),
      "unknown kind = 404")

print(f"OK {ok} checks")
shutil.rmtree(HOME, ignore_errors=True)
