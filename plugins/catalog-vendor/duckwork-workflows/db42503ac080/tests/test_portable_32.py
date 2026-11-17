#!/usr/bin/env python3
"""#32 publish-as-file: the portable workflow file convention.

(1) top-level `grammar` — "wf/1" accepted; an unknown value is REFUSED (before any
    write/spawn) with the supported list named in the error; absent = wf/1 and the
    graph still RUNS (door run with the fake launcher reaches done).
(2) `grammar` is a top-level annotation: def_hash / efp / graph_fingerprint /
    source_digest are byte-identical with and without it (golden-solo law).
(3) examples/review/portable-review.workflow.json validates, and BOTH digests pinned in
    references/portable.md (file sha256 + nodes source_digest) equal the file's.
Hermetic: fake launcher, sandboxed HOME.
"""
import hashlib, importlib.util, json, os, re, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-portable32"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(HERE / "fake")
(HOME / "config.yaml").write_text("model:\n  default: seat-default\n")
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402
spec = importlib.util.spec_from_file_location("door32", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, msg + (f"  << {detail}" if detail else "")
    ok += 1; print("PASS", msg)

def call(**a):
    return json.loads(door.handle(a))

NODES = [{"id": "a", "type": "agent", "goal": "say hi", "max_turns": 2},
         {"id": "b", "type": "agent", "after": ["a"], "goal": "say bye", "max_turns": 2}]
plain = {"name": "g32", "nodes": json.loads(json.dumps(NODES))}
tagged = {"name": "g32", "grammar": "wf/1", "nodes": json.loads(json.dumps(NODES))}

# --- (1) validator: supported / absent / unknown -----------------------------------
check(wfcommon.validate_graph_errors(tagged) == [], "grammar wf/1 accepted by validate_graph_errors")
check(wfcommon.validate_graph_errors(plain) == [], "absent grammar accepted (wf/1 back-compat)")
check(wfcommon.validate_graph_errors(NODES) == [], "bare node list still validates unchanged")
supported = json.dumps(list(wfcommon.GRAMMAR_SUPPORTED))
for bad in ("wf/2", "anthropic/js", "", 1, None):
    errs = wfcommon.validate_graph_errors({"grammar": bad, "nodes": NODES})
    check(len(errs) == 1 and errs[0]["node"] is None and errs[0]["field"] == "grammar",
          f"unknown grammar {bad!r} -> exactly one top-level grammar error", errs)
    check(supported in errs[0]["msg"] and "wf/1" in errs[0]["msg"],
          f"unknown grammar {bad!r} error names the supported list {supported}", errs[0]["msg"])
errs = wfcommon.validate_graph_errors({"grammar": "wf/9", "nodes": []})
check([e["field"] for e in errs] == ["grammar", "nodes"],
      "grammar error is reported alongside a nodes defect, not instead of it", errs)

# door: unknown grammar refused BEFORE any run dir exists
runs = HOME / "workflows"
r = call(action="run", graph={"name": "g32", "grammar": "wf/2", "nodes": NODES})
check("run_id" not in r and r.get("error"), "door refuses unknown grammar", json.dumps(r))
fields = [e.get("field") for e in r.get("errors", [])]
check("grammar" in fields and any(supported in e["msg"] for e in r["errors"]),
      "door error lists field=grammar and the supported values", json.dumps(r))
check(not runs.exists() or not any(runs.iterdir()), "refusal wrote no run dir")
r = call(action="save", graph={"name": "g32", "grammar": "wf/2", "nodes": NODES}, name="bad-grammar")
check("saved" not in r and "grammar" in json.dumps(r), "save refuses unknown grammar too", json.dumps(r))

# door: absent grammar still RUNS to done; tagged wf/1 runs too
for label, g in (("absent", plain), ("wf/1", tagged)):
    r = call(action="run", graph=g)
    rid = r.get("run_id")
    check(bool(rid), f"grammar {label}: run launches", json.dumps(r))
    st = call(action="wait", run_id=rid, timeout=60)
    check(st.get("status") == "done", f"grammar {label}: run reaches done", json.dumps(st)[:400])
    committed = json.load(open(runs / rid / "graph.json"))
    check(("grammar" in committed) == (label == "wf/1"),
          f"grammar {label}: committed graph.json keeps the author's top-level bytes")

# --- (2) def_hash neutrality: identical fingerprints with/without the annotation ----
byid_p = {n["id"]: n for n in plain["nodes"]}
byid_t = {n["id"]: n for n in tagged["nodes"]}
for nid in byid_p:
    check(wfcommon.def_hash(byid_p[nid]) == wfcommon.def_hash(byid_t[nid]),
          f"def_hash({nid}) equal with and without grammar")
    check(wfcommon.efp(byid_p, byid_p[nid]) == wfcommon.efp(byid_t, byid_t[nid]),
          f"efp({nid}) equal with and without grammar")
check(wfcommon.graph_fingerprint(plain) == wfcommon.graph_fingerprint(tagged),
      "graph_fingerprint equal with and without grammar")
check(wfcommon.source_digest(plain) == wfcommon.source_digest(tagged),
      "source_digest equal with and without grammar")
# and the committed node defs the runner hashed are byte-equal across the two runs
runs_sorted = wfcommon.iter_run_dirs(runs)  # .seats (est-g2xx) is never a run
defs = [json.dumps(json.load(open(p / "graph.json"))["nodes"], sort_keys=True) for p in runs_sorted]
check(len(defs) == 2 and defs[0] == defs[1], "committed node defs byte-equal across absent/wf/1 runs")

# --- (3) walk-in example validates and matches the doc-pinned digests -------------
example = ROOT / "examples" / "review" / "portable-review.workflow.json"
doc = (ROOT / "references" / "portable.md").read_text(encoding="utf-8")
raw = example.read_bytes()
graph = json.loads(raw)
check(graph.get("grammar") == "wf/1", "example declares grammar wf/1")
check(wfcommon.validate_graph_errors(graph) == [], "example validates (shared validator)",
      wfcommon.validate_graph_errors(graph))
check(door._validation_error(graph) is None, "example validates (door, incl. provenance keys)",
      json.dumps(door._validation_error(graph)))
check(example.name.endswith(".workflow.json"), "example follows <name>.workflow.json")
pins = re.findall(r"`([0-9a-f]{64})`", doc)
check(len(pins) == 2, "doc pins exactly two 64-hex digests", pins)
file_sha, nodes_digest = pins
check(file_sha == hashlib.sha256(raw).hexdigest(), "doc-pinned file sha256 == sha256(example bytes)",
      hashlib.sha256(raw).hexdigest())
check(nodes_digest == wfcommon.source_digest(graph), "doc-pinned source_digest == source_digest(example)",
      wfcommon.source_digest(graph))
check("examples/review/portable-review.workflow.json" in doc and "NO code" in doc,
      "doc names the example and states that a wf/1 file carries no code")

shutil.rmtree(HOME, ignore_errors=True)
print(f"OK {ok} checks")
