"""Lane B v0.7.6 contracts (Q2/Q3/Q5 + read model):
(1) validate_graph_errors returns EVERY defect as {node, field, msg}; unknown
    node/fanout/wait keys rejected with the allowed list; validate_graph keeps the
    old first-error-string signature; run/amend return error+errors together.
(2) door JSON-string graphs parse with the malformed spot quoted ±40 chars.
(3) amend dry_run:true returns {added, removed, changed, will_rerun, unchanged} from
    the committed graph plus efp/node_rec without touching graph.json/amends.jsonl/the runner;
    normal amend echoes the same impact.
(4) node.reasoning validated against ('none',)+duckwork_constants.VALID_REASONING_EFFORTS
    — BOTH import paths (real duckwork_constants AND the fallback literal) exercised.
(5) amend previews report added/removed graph ids and new downstream work, including
    never-started affected nodes, without changing replay-skip or dry-run purity.
(6) run_state/act_status/dashboard surface runner_exit from <run>/runner_exit.json,
    or 'crashed (no exit record)' when wf.pid is dead and the file is absent.
"""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import glob, importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
home = HERE / "home11"
if home.exists():
    shutil.rmtree(home)
home.mkdir()
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(home / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(HERE / "fake")
(home / "config.yaml").write_text("model:\n  default: seat-default\n")
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402
sys.modules.pop("duckwork_cli.config", None)
spec = importlib.util.spec_from_file_location("door9", BUILD / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
sys.path.insert(0, str(BUILD / "dashboard"))
import plugin_api  # noqa: E402

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}" + (f"  << {detail}" if detail and cond is not True else "")
    ok += 1; print("PASS", msg)

V  = lambda nodes: wfcommon.validate_graph_errors(nodes)
Vs = lambda nodes: wfcommon.validate_graph(nodes)

# --- (1) error shape: every defect is {node, field, msg} ---
agent = lambda **kw: {"id": "a", "type": "agent", **kw}
errs = V([{"id": "a", "type": "agent"}])                       # no goal
check(errs and all(set(e) == {"node", "field", "msg"} for e in errs),
      "errors are exactly {node, field, msg} dicts", errs)
check(errs and errs[0]["node"] == "a" and errs[0]["field"] == "goal" and "goal" in errs[0]["msg"],
      "missing goal names node+field", errs)
check(Vs([{"id": "a", "type": "agent"}]) == "node a: agent node has no goal",
      "validate_graph wrapper keeps the old 'node X: …' string signature")
check(V([{"id": "a", "type": "agent", "goal": "x"}, {"id": "b", "type": "gate", "question": "q"}]) == [],
      "clean graph -> empty error list")
# every error class, all in ONE call
many = V([
    {"id": "a", "type": "weird"},                                        # bad type
    {"id": "b", "type": "agent"},                                        # no goal
    {"id": "c", "type": "agent", "goal": "g", "after": ["ghost"],        # unknown after
     "timeout": 0},                                                      # bad timeout
    {"id": "d", "type": "agent", "goal": "g", "schema": 5},              # schema not object
])
check(len(many) == 5 and {e["node"] for e in many} == {"a", "b", "c", "d"},
      "multiple defects across nodes returned TOGETHER", many)
check(any("type must be agent|gate" in e["msg"] for e in many)
      and any(e["field"] == "after" and "ghost" in e["msg"] for e in many)
      and any(e["field"] == "timeout" for e in many)
      and any(e["field"] == "schema" for e in many),
      "error classes: type / after / timeout / schema each named", many)
dup = V([{"id": "x", "type": "agent", "goal": "g"}, {"id": "x", "type": "agent", "goal": "g"}])
check(any("duplicate" in e["msg"] for e in dup), "duplicate ids rejected", dup)
check(any("'x'" in e["msg"] or '"x"' in e["msg"] for e in dup),
      "duplicate-id error NAMES the duplicated id", dup)
cyc = V([{"id": "p", "type": "agent", "goal": "g", "after": ["q"]},
         {"id": "q", "type": "agent", "goal": "g", "after": ["p"]}])
check(any("cycle" in e["msg"] for e in cyc), "cycle rejected", cyc)
check(any("cycle" in e["msg"] and "'p'" in e["msg"] and "'q'" in e["msg"] for e in cyc),
      "cycle error NAMES the stuck nodes", cyc)
# missing type surfaces alongside every other defect, not instead of them
no_type = V([{"id": "m", "goal": "g", "after": ["ghost"], "timeout": 0}])
check(any(e["field"] == "type" for e in no_type)
      and any(e["field"] == "after" and "ghost" in e["msg"] for e in no_type)
      and any(e["field"] == "timeout" for e in no_type),
      "missing type reports type + after + timeout in ONE pass (no early continue)", no_type)
bad_when = V([{"id": "g", "type": "gate", "question": "q", "when": "out.j.v == "}])
check(any(e["field"] == "when" and "out.<node>" in e["msg"] and "and/or/not" in e["msg"]
          for e in bad_when),
      "when rejection quotes the bounded grammar one-liner", bad_when)
bad_id = V([{"id": "-nope", "type": "agent", "goal": "g"}])
check(any(e["field"] == "id" and "invalid node id" in e["msg"] for e in bad_id),
      "invalid node id rejected", bad_id)
weak_ids = V([{"id": 7, "type": "agent", "goal": "g"}])          # would TypeError pre-guard
check(weak_ids and weak_ids[0]["field"] == "id" and "invalid node id" in weak_ids[0]["msg"],
      "non-string id rejected without crashing the validator", weak_ids)

# --- (2) unknown keys REJECTED with the allowed list ---
e = V([{"id": "a", "type": "agent", "goal": "g", "colour": "blue"}])
check(len(e) == 1 and e[0]["field"] == "colour" and "unknown key" in e[0]["msg"]
      and '"colour"' not in e[0]["msg"].split("allowed")[1]
      and all(k in e[0]["msg"] for k in ("goal", "fanout", "reasoning", "max_turns")),
      "unknown agent key rejected with the allowed list", e)
e = V([{"id": "g", "type": "gate", "question": "q", "goal": "smuggle"}])
check(any(e0["field"] == "goal" and "unknown key" in e0["msg"] and '"question"' in e0["msg"]
          for e0 in e), "unknown gate key rejected with the GATE allowed list", e)
e = V([{"id": "f", "type": "agent", "goal": "g", "fanout": {"items": ["x"], "shard_by": "host"}}])
check(any(e0["field"] == "fanout.shard_by" and "unknown key" in e0["msg"]
          and "items_from" in e0["msg"] and "quorum" in e0["msg"] for e0 in e),
      "unknown fan-out sub-key rejected with its allowed list", e)
e = V([{"id": "g", "type": "gate", "after": [], "question": "q", "wait": {"cmd": "ls"}}])
check(any(e0["field"] == "wait.cmd" and "unknown key" in e0["msg"] and "until_argv" in e0["msg"]
          for e0 in e), "unknown wait sub-key rejected with its allowed list", e)
check(Vs([{"id": "a", "type": "agent", "goal": "g", "wait": {"wait_s": 1}}])
      == "node a: only gate nodes take wait", "agent+wait keeps its dedicated error, not unknown-key")
check(Vs([{"id": "a", "type": "agent", "goal": "g"},
          {"id": "g", "type": "gate", "after": ["a"], "question": "q", "inputs": ["a"]}])
      == "node g: gates cannot have inputs", "gate+inputs keeps its dedicated error, not unknown-key")

# --- (3) self-contained compatibility corpus from the checked-in examples.
# Never compare against an untracked source backup or inspect the user's Duckwork home.
# Validate the portable examples actually shipped in the source archive. The
# two host-specific historical drafts are intentionally excluded from packaging
# and retain unsupported schema types; they are not compatibility fixtures.
graphs = [next((BUILD / "examples").rglob(f"{name}.json")) for name in
          ("approve-publish", "blind-council.workflow", "branch-on-verdict", "incident-response", "smoke",
           "gated-publish.workflow", "machine-watch.workflow", "triage-route.workflow", "quorum-probe.workflow", "bulk-transform.workflow", "escalation-ladder.workflow",
           "census-fanout.workflow", "exchange-run.workflow", "release-lifecycle.workflow", "issue-to-pr.workflow", "submit-pr.workflow")]
bad_graphs = []
for f in graphs:
    try:
        g = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        bad_graphs.append((f.name, str(e)))
        continue
    if not g.get("nodes"):
        bad_graphs.append((f.name, "missing nodes"))
        continue
    errs = V(g["nodes"])
    if errs:
        bad_graphs.append((f.name, errs))
check(bool(graphs) and not bad_graphs,
      f"all {len(graphs)} checked-in compatibility examples parse and validate", str(bad_graphs[:2]))

# --- (4) reasoning per node (Q5) ---
import duckwork_constants  # noqa: E402  (venv has core on path — the REAL import path)
GOOD = ["none"] + list(duckwork_constants.VALID_REASONING_EFFORTS)
check(V([agent(goal="g", reasoning="none")]) == []
      and all(V([agent(goal="g", reasoning=lv)]) == [] for lv in GOOD),
      "reasoning accepts 'none' + every VALID_REASONING_EFFORTS value", GOOD)
e = V([agent(goal="g", reasoning="supreme")])
check(len(e) == 1 and e[0]["field"] == "reasoning" and "unknown" not in e[0]["msg"]
      and "supreme" in e[0]["msg"] and "ultra" in e[0]["msg"],
      "invalid reasoning rejected with the allowed list", e)
check(wfcommon.REASONING_IMPORT_PATH[0] == "duckwork_constants",
      "primary test run used the duckwork_constants import path", wfcommon.REASONING_IMPORT_PATH)
# fallback path: force the import to fail, exercise the literal, restore
_saved = sys.modules.pop("duckwork_constants", None)
sys.modules["duckwork_constants"] = None  # makes `import duckwork_constants` raise ImportError
try:
    fb = wfcommon.reasoning_levels()
    check(fb == wfcommon.REASONING_FALLBACK
          and wfcommon.REASONING_IMPORT_PATH[0] == "fallback-literal",
          "fallback literal == ('none',)+VALID_REASONING_EFFORTS and was exercised", fb)
    check(fb == tuple(GOOD),
          "fallback literal matches the live core tuple", fb)
finally:
    sys.modules.pop("duckwork_constants", None)
    if _saved is not None:
        sys.modules["duckwork_constants"] = _saved
doc = door.WORKFLOW_PARAMS["properties"]["graph"]["description"]
check("reasoning" in doc and "--reasoning" in doc,
      "tool schema documents the reasoning field in one line")

# --- (5) door: structured errors + JSON-string graphs quoted ---
call = lambda **a: json.loads(door.handle(a))
r = call(action="run", graph={"name": "x", "nodes": [{"id": "a", "type": "agent"},
                                                     {"id": "b", "type": "nope"}]})
check(r.get("error", "").startswith("graph invalid: node a")
      and isinstance(r.get("errors"), list) and len(r["errors"]) == 2
      and all(set(e) == {"node", "field", "msg"} for e in r["errors"]),
      "run returns first-message 'error' + ALL 'errors' together", r)
r = call(action="run", graph=json.dumps({"name": "x", "nodes": "not-a-list"}))
check(r.get("error", "").startswith("graph invalid") and isinstance(r.get("errors"), list),
      "door PARSES a string graph and validates it", r)
malformed = '{"name": "x", "nodes": [{"id": "a", "type": "agent", "goal": "x"},}'
r = call(action="run", graph=malformed)
check(r.get("error", "").startswith("graph is not valid JSON") and "near" in r
      and "goal" in r["near"] and r["near"].startswith("…") and r["near"].endswith("…")
      and len(r["near"]) - 2 <= 80,
      "malformed string graph quoted ±40 chars around the offset", r)
r = call(action="run", graph="[oops")
check("graph is not valid JSON" in r.get("error", "") and r.get("near", "").startswith("…"),
      "offset-0 parse error still quoted", r)
N = lambda: {"name": "n", "nodes": [{"id": "a", "type": "agent", "goal": "OK"}]}
check(call(action="run", graph=N()).get("run_id"),
      "string form of a valid graph runs (parse-then-run works)")
r = call(action="run", graph=42)
check("must be an object" in r.get("error", ""), "non-dict graph rejected honestly", r)

# --- (6) amend preview (Q3): half-finished run, efp-backed records by hand ---
def mkrun(name, graph, done=None, run_meta=None):
    r = home / "workflows" / name
    (r / "nodes").mkdir(parents=True, exist_ok=True)
    (r / "gates").mkdir(exist_ok=True)
    (r / "graph.json").write_text(json.dumps(graph))
    (r / "run.json").write_text(json.dumps(run_meta or {"name": name, "duckwork_bin": str(HERE / "fake")}))
    byid = {n["id"]: n for n in graph["nodes"]}
    for nid in (done or []):
        st = "done"
        (r / "nodes" / f"{nid}.json").write_text(json.dumps(
            {"status": st, "output": {"result": "ok"}, "efp": wfcommon.efp(byid, byid[nid]),
             "skey": f"wf:{name}:{nid}:00000000.aaaaaa", "attempts": 1, "ms": 5}))
    return r

G = {"name": "prev", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "b", "type": "agent", "after": ["a"], "goal": "OK"},
    {"id": "g", "type": "gate", "after": ["b"], "question": "ship?"},
    {"id": "c", "type": "agent", "after": ["g"], "goal": "OK"},
    {"id": "d", "type": "agent", "goal": "OK"},               # independent branch
]}
# half-finished: a and d committed correctly for G; b/g/c never ran (no records)
r = mkrun("20990101-000000-prev", G, done=["a", "d"])
g2 = json.loads(json.dumps(G)); g2["nodes"][0]["goal"] = "OK v2"   # amend the ROOT of the chain
p = call(action="amend", run_id=r.name, graph=g2, dry_run=True)
check(p.get("ok") and p.get("dry_run")
      and p["changed"] == ["a"]
      and p["will_rerun"] == ["a", "b", "g", "c"]
      and p["unchanged"] == ["d"],
      "dry_run: changed=[efp-mismatched commit], will_rerun=changed+downstream (pending-or-not), unchanged=replay-skip", p)
check(json.loads((r / "graph.json").read_text()) == G
      and not (r / "amends.jsonl").exists() and not (r / "restart.request").exists(),
      "dry_run touched NOTHING: graph.json bytes identical, no amends.jsonl, no restart.request")
# spawn-time 'running' record (Lane A's contract) is NEVER mistaken for a commit
(r / "nodes" / "b.json").write_text(json.dumps(
    {"status": "running", "pid": 99999, "efp": wfcommon.efp({n["id"]: n for n in G["nodes"]}, G["nodes"][1])}))
st, _ = wfcommon.node_rec(r, G["nodes"][1], {n["id"]: n for n in G["nodes"]})
check(st == "pending", "status:'running' record is pending for node_rec (safe by construction)")
p2 = call(action="amend", run_id=r.name, graph=g2, dry_run=True)
check(p2["will_rerun"] == ["a", "b", "g", "c"] and p2["unchanged"] == ["d"],
      "a stale 'running' record still counts as not-done in the preview", p2)
(r / "nodes" / "b.json").unlink()

# A correctly identified fixture runner keeps amend on its hot-reload path.
_sleeper = r.parent.parent / "wf.py"
_sleeper.write_text("import time\ntime.sleep(120)\n")
_live = subprocess.Popen([sys.executable, str(_sleeper), "run", r.name],
                         env={**os.environ, "DUCKWORK_HOME": str(r.parent.parent)})
(r / "wf.pid").write_text(str(_live.pid))
try:
    am = call(action="amend", run_id=r.name, graph=json.loads(json.dumps(g2)))
    check(am.get("ok") and "hot-reloads" in am.get("applies", "")
          and (r / "restart.request").exists(),
          "normal amend echoes applies=hot-reload (no respawn) when runner is live", am)
finally:
    _live.terminate(); _live.wait()
    (r / "wf.pid").unlink(missing_ok=True)
check(am["changed"] == p["changed"] and am["will_rerun"] == p["will_rerun"]
      and am["unchanged"] == p["unchanged"],
      "normal amend response carries the SAME three lists as the preview", am)
check(json.loads((r / "graph.json").read_text())["nodes"][0]["goal"] == "OK v2",
      "normal amend actually wrote the new graph")
# commit the chain under g2 (as the runner would), then a no-op amend replays everything
_byid2 = {n["id"]: n for n in g2["nodes"]}
for _nid in ("a", "b", "g", "c"):
    (r / "nodes" / f"{_nid}.json").write_text(json.dumps(
        {"status": "done", "output": {"result": "ok"},
         "efp": wfcommon.efp(_byid2, _byid2[_nid]), "attempts": 1, "ms": 5}))
p3 = call(action="amend", run_id=r.name, graph=json.loads(json.dumps(g2)), dry_run=True)
check(p3["changed"] == [] and p3["will_rerun"] == []
      and p3["unchanged"] == ["a", "b", "g", "c", "d"],
      "same-graph dry_run after commits: everything replays-skip", p3)
# failed-with-matching-efp is neither changed nor unchanged (the grammar is efp-first)
(r / "nodes" / "b.json").write_text(json.dumps(
    {"status": "failed", "error": "boom", "efp": wfcommon.efp(_byid2, _byid2["b"])}))
p4 = call(action="amend", run_id=r.name, graph=json.loads(json.dumps(g2)), dry_run=True)
check("b" not in p4["changed"] and "b" not in p4["unchanged"],
      "matching-efp FAILED record: not 'changed', not 'unchanged'", p4)
# invalid graph is refused even in dry_run, with the structured list
p5 = call(action="amend", run_id=r.name, graph={"name": "z", "nodes": [{"id": "a", "type": "agent"}]},
          dry_run=True)
check(p5.get("error", "").startswith("graph invalid") and len(p5.get("errors", [])) == 1
      and json.loads((r / "graph.json").read_text())["nodes"][0]["goal"] == "OK v2",
      "dry_run validates first and still touches nothing", p5)

# Added work is explicit; removed ids cannot be executed; unchanged pending ids
# stay out unless affected. Exercise both real amend paths (not just the helper).
Gadd = {"name": "add-impact", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "d", "type": "agent", "goal": "OK"},
    {"id": "gone", "type": "agent", "goal": "OK"},
    {"id": "p", "type": "agent", "after": ["a"], "goal": "OK"},
    {"id": "q", "type": "agent", "after": ["p"], "goal": "OK"},
    {"id": "never", "type": "agent", "goal": "OK"},
]}
radd = mkrun("20990101-000002-add-impact", Gadd, done=["a", "d", "gone"])
Gadd2 = {"name": "add-impact", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "d", "type": "agent", "goal": "OK"},
    {"id": "new", "type": "agent", "after": ["a"], "goal": "NEW WORK"},
    {"id": "p", "type": "agent", "after": ["new"], "goal": "OK"},
    {"id": "q", "type": "agent", "after": ["p"], "goal": "OK"},
    {"id": "never", "type": "agent", "goal": "OK"},
]}
padd = call(action="amend", run_id=radd.name, graph=Gadd2, dry_run=True)
check(padd.get("ok") and padd.get("added") == ["new"] and padd.get("removed") == ["gone"]
      and padd["changed"] == ["p"] and padd["will_rerun"] == ["new", "p", "q"]  # est-c9is: p re-parented a->new = def drift
      and padd["unchanged"] == ["a", "d"] and "never" not in padd["will_rerun"],
      "dry_run reports added/removed ids, new downstream work, and excludes unaffected never-started node", padd)
check(json.loads((radd / "graph.json").read_text()) == Gadd
      and not (radd / "amends.jsonl").exists() and not (radd / "restart.request").exists()
      and not (radd / "wf.pid").exists(),
      "added-node dry_run remains side-effect free")
_add_live = subprocess.Popen([sys.executable, str(_sleeper), "run", radd.name],
                             env={**os.environ, "DUCKWORK_HOME": str(radd.parent.parent)})
(radd / "wf.pid").write_text(str(_add_live.pid))
try:
    amadd = call(action="amend", run_id=radd.name, graph=Gadd2)
finally:
    _add_live.terminate(); _add_live.wait()
    (radd / "wf.pid").unlink(missing_ok=True)
check(amadd.get("ok") and amadd.get("added") == padd["added"]
      and amadd.get("removed") == padd["removed"]
      and amadd["changed"] == padd["changed"]
      and amadd["will_rerun"] == padd["will_rerun"]
      and amadd["unchanged"] == padd["unchanged"]
      and json.loads((radd / "graph.json").read_text()) == wfcommon.apply_graph_defaults(Gadd2),
      "normal amend applies the RESOLVED graph (defaults/shape baked) and echoes the exact preview impact", amadd)

# --- (7) runner_exit read model ---
import re as _re
rid = "20990101-000001-exit"
r = mkrun(rid, {"name": "exit", "nodes": [{"id": "a", "type": "agent", "goal": "OK"}]}, done=["a"])
# dead pid, no record => crashed
dead = subprocess.Popen([sys.executable, "-c", "pass"]); dead.wait()
(r / "wf.pid").write_text(str(dead.pid))
check(wfcommon.run_state(r)["runner_exit"] == {"reason": "crashed (no exit record)"},
      "dead wf.pid + no runner_exit.json => crashed (no exit record)")
st = door.act_status({"run_id": rid})
check(st.get("runner_exit") == {"reason": "crashed (no exit record)"},
      "act_status surfaces the crash note", st.get("runner_exit"))
v = plugin_api._view(r, full=True)
check(v.get("runner_exit") == {"reason": "crashed (no exit record)"},
      "dashboard full view surfaces the crash note", v.get("runner_exit"))
# A current-graph exit record wins over the liveness heuristic.
exit_record = {"reason": "blocked by failed a", "at": "2099-01-01T00:00:00+00:00", "detail": "x",
               "graph_fingerprint": wfcommon.graph_fingerprint(json.loads((r / "graph.json").read_text())),
               "fp_rule_version": wfcommon.FP_RULE_VERSION}
(r / "runner_exit.json").write_text(json.dumps(exit_record))
st = door.act_status({"run_id": rid})
# Ledger 95d7010295d70102: the stamped record verifies under its own rule;
# the public read model intentionally projects only verdict fields, not provenance.
check(st.get("runner_exit") == {k: v for k, v in exit_record.items() if k != "fp_rule_version"},
      "act_status surfaces the validated graph-bound runner_exit projection", st.get("runner_exit"))
check(plugin_api._view(r, full=True).get("runner_exit", {}).get("reason") == "blocked by failed a",
      "dashboard full view surfaces the exit record")
# live pid, no record => not a crash
live = subprocess.Popen([sys.executable, str(_sleeper), "run", r.name],
                        env={**os.environ, "DUCKWORK_HOME": str(r.parent.parent)})
try:
    (r / "runner_exit.json").unlink()
    (r / "wf.pid").write_text(str(live.pid))
    check(wfcommon.run_state(r)["runner_exit"] is None,
          "live pid + no record => no crash claim (None)")
    # but if the record exists it is surfaced even while live
    current_done = {"reason": "done", "graph_fingerprint": exit_record["graph_fingerprint"],
                    "fp_rule_version": wfcommon.FP_RULE_VERSION}
    (r / "runner_exit.json").write_text(json.dumps(current_done))
    check(wfcommon.run_state(r)["runner_exit"] == {k: v for k, v in current_done.items() if k != "fp_rule_version"},
          "validated graph-bound verdict beats liveness while pid is alive")
    (r / "runner_exit.json").write_text(json.dumps({"reason": "done"}))
    check(wfcommon.run_state(r)["runner_exit"]["reason"] == "stale",
          "unversioned exit cannot claim current completion")
    (r / "runner_exit.json").unlink()
    check(door.act_status({"run_id": rid}).get("runner_exit") is None,
          "act_status omits runner_exit when there is nothing to say")
finally:
    live.terminate(); live.wait()
# no wf.pid file at all (fresh run pre-spawn) => no crash claim
(r / "wf.pid").unlink()
check(wfcommon.run_state(r)["runner_exit"] is None,
      "no wf.pid yet => None, not a false crash")
# corrupt pid file => counts dead
(r / "wf.pid").write_text("not-a-pid")
check(wfcommon.run_state(r)["runner_exit"] == {"reason": "crashed (no exit record)"},
      "corrupt wf.pid counts as dead (honest crash, never silent)")

print(f"\nALL PASS ({ok})")
