#!/usr/bin/env python3
"""#59 — string-type holes in the submit validator (fb-fix ledger 97e90c2205f17fb0).

Repro (run 20260930-051209-fb-fix-436f89c3-rem): agent `context` authored as a LIST
passed validate_graph_errors, then the FIRST spawn crashed in wf.py run_child:
    prompt = goal + ("\\n\\n" + context ...)
    -> node crashed: TypeError: can only concatenate str (not "list") to str
The gate release that unblocked that node was burned on a node that died pre-child.

Law (issue #59): strict-at-submit — TYPE validation with named-node E(nid, field,
msg) errors, mirroring the fan-out item-goal check style; NO coercion at resolve
(wfcommon.py closed-grammar law — an un-validatable graph must never be accepted).

Covers: agent goal (truthy non-str + whitespace-only str rejected; the falsy case
keeps its exact legacy message), agent AND gate context, gate question, echo output
(must be JSON-typed: the door commits it via json.dumps at run-dir write — a set/
custom object crashes there; dict/list/str/num/bool/null stay legal verbatim-commit
shapes), and the fan-out goal template (fmt_goal re.sub + node-goal concat, same
crash class — R8 sibling). Plus the door-level law: a rejecting submit writes ZERO
run dirs.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import wfcommon  # noqa: E402

spec = importlib.util.spec_from_file_location("wf_door_59", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

ok = 0
def check(cond, name):
    global ok
    print(("PASS" if cond else "FAIL"), "-", name)
    ok += 1 if cond else 0
    if not cond:
        raise SystemExit(1)

V = wfcommon.validate_graph_errors


def fields(errs, nid):
    return sorted({e["field"] for e in errs if e["node"] == nid})


# --- the exact repro: context authored as a list -----------------------------
repro = [{"id": "impl", "type": "agent", "goal": "do the work", "context": ["a", "b"]}]
errs = V(repro)
check(any(e["node"] == "impl" and e["field"] == "context"
         and "must be a string" in e["msg"] for e in errs),
      "issue repro: agent context ['a','b'] rejected at submit naming node+field")

# --- agent goal ---------------------------------------------------------------
check(V([{"id": "a", "type": "agent"}]) == [{'node': 'a', 'field': 'goal',
                                             'msg': 'agent node has no goal'}],
      "falsy goal keeps the exact 'agent node has no goal' message (no regression)")
check(V([{"id": "a", "type": "agent", "goal": ""}]) == [{'node': 'a', 'field': 'goal',
                                                         'msg': 'agent node has no goal'}],
      "empty-string goal keeps the exact 'agent node has no goal' message")
for bad_goal in ([ "do", "it" ], {"t": "x"}, 42, True):
    errs = V([{"id": "a", "type": "agent", "goal": bad_goal}])
    check(any(e["node"] == "a" and e["field"] == "goal"
              and "must be a non-empty string" in e["msg"] for e in errs),
          f"goal {bad_goal!r} rejected as non-string")
errs = V([{"id": "a", "type": "agent", "goal": "   \n " }])
check(any(e["node"] == "a" and e["field"] == "goal" for e in errs),
      "whitespace-only goal rejected (whitespace-only law, mirrors fanout item goal)")
# ra-59 review finding 1: PRESENT falsy non-str goals — checked independently of
# truthiness, incl. as the fan-out prefix goal (first cut let [] {} 0 False through
# to a created run dir when items supplied their own goals).
for falsy in ([], {}, 0, False, None):
    errs = V([{"id": "a", "type": "agent", "goal": falsy}])
    check(any(e["node"] == "a" and e["field"] == "goal"
              and "must be a non-empty string" in e["msg"] for e in errs),
          f"present falsy/null goal {falsy!r} rejected (truthiness-independent)")
    errs = V([{"id": "f", "type": "agent", "goal": falsy,
               "fanout": {"items": [{"goal": "work"}]}}])
    check(any(e["node"] == "f" and e["field"] == "goal"
              and "must be a non-empty string" in e["msg"] for e in errs),
          f"fan-out prefix goal {falsy!r} rejected, items-goal does not excuse it")
check(V([{"id": "f", "type": "agent", "fanout": {"items": [{"goal": "work"}]}}]) == [],
      "fan-out with OMITTED node goal and valid item goals stays legal")
check(V([{"id": "f", "type": "agent", "goal": "join",
          "fanout": {"items": [{"goal": "a"}, {"goal": "b"}]}}]) == [],
      "omitted fanout.goal (items supply goals) stays legal — falsy law is type-only")

# --- context on agent AND gate ------------------------------------------------
errs = V([{"id": "a", "type": "agent", "goal": "x", "context": {"k": 1}}])
check(any(e["node"] == "a" and e["field"] == "context" for e in errs),
      "agent context dict rejected")
errs = V([{"id": "a", "type": "agent", "goal": "x", "context": ""}])
check(not any(e["field"] == "context" for e in errs),
      "agent context '' (absent-equivalent, falsy) stays legal")
errs = V([{"id": "a", "type": "agent", "goal": "x"},
          {"id": "g", "type": "gate", "after": ["a"], "context": ["preamble"]}])
check(any(e["node"] == "g" and e["field"] == "context" and "must be a string" in e["msg"]
          for e in errs),
      "gate context list rejected naming node+field")

# --- gate question ------------------------------------------------------------
errs = V([{"id": "a", "type": "agent", "goal": "x"},
          {"id": "g", "type": "gate", "after": ["a"], "question": {"q": "?"}}])
check(any(e["node"] == "g" and e["field"] == "question" for e in errs),
      "gate question dict rejected")
errs = V([{"id": "a", "type": "agent", "goal": "x"},
          {"id": "g", "type": "gate", "after": ["a"], "question": 7}])
check(any(e["node"] == "g" and e["field"] == "question" for e in errs),
      "gate question int rejected")
errs = V([{"id": "a", "type": "agent", "goal": "x"},
          {"id": "g", "type": "gate", "after": ["a"], "question": "",
           "context": "ctx"}])
check(not any(e["field"] == "question" for e in errs),
      "gate question '' (optional key, falsy) stays legal")

# --- echo output: must be JSON-typed (the door commits it via json.dumps) ----
for good in ({"ok": True}, ["a", 1], "text", 42, True, None):
    errs = V([{"id": "e", "type": "echo", "output": good}])
    check(not any(e["field"] == "output" for e in errs),
          f"echo output {type(good).__name__} stays legal (verbatim-commit shapes)")
class Weird:  # not JSON-serialisable — exactly what used to crash the door at write
    pass
for bad_out in (Weird(), {1, 2, 3}):
    errs = V([{"id": "e", "type": "echo", "output": bad_out}])
    check(any(e["node"] == "e" and e["field"] == "output" for e in errs),
          f"echo output {type(bad_out).__name__} rejected at submit (JSON-typed law)")

# --- fan-out goal template: same crash class (fmt_goal re.sub + node-goal concat)
errs = V([{"id": "f", "type": "agent", "goal": "join",
           "fanout": {"items": ["x"], "goal": ["render", "{item}"]}}])
check(any(e["node"] == "f" and e["field"] == "fanout.goal"
          and "non-empty string" in e["msg"] for e in errs),
      "fanout.goal list rejected naming node+field (R8 sibling of the goal law)")

# --- the law: no coercion — a graph with a bad string field never reaches resolve
check(V([{"id": "a", "type": "agent", "goal": "x", "context": ["a"]}]) != [],
      "no list->join coercion at resolve: reject stands")

# --- valid graphs validate CLEAN (strictly additive; golden-solo EMPTY law) ---
check(V([{"id": "a", "type": "agent", "goal": "x", "context": "preamble"},
         {"id": "g", "type": "gate", "after": ["a"], "question": "Ship?",
          "options": ["yes", "no"], "context": "why"},
         {"id": "e", "type": "echo", "after": ["g"], "output": {"joined": True}},
         {"id": "f", "type": "agent", "after": ["e"], "goal": "join",
          "fanout": {"items_from": "e.joined", "goal": "item {item}"}}]) == [],
      "valid graph (all string fields well-typed) validates with ZERO errors")

# --- door law: a rejecting submit writes ZERO run dirs -------------------------
tmp = tempfile.TemporaryDirectory(prefix="wf59-")
root = Path(tmp.name)
runs = root / "runs"          # WF_RUNS_ROOT: must not exist after a reject
env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(runs),
                              "DUCKWORK_HOME": str(root / "home")})
env.start()
spawn_pings = []
spawn = patch.object(door, "_spawn_runner", side_effect=lambda r: spawn_pings.append(r))
spawn.start()
try:
    bad = {"name": "typehole-59",
           "nodes": [{"id": "impl", "type": "agent", "goal": "work",
                      "context": ["a", "b"]}]}
    res = door.act_run({"graph": json.loads(json.dumps(bad))})
    check(res.get("error", "").startswith("graph invalid:"),
          "door act_run rejects the context-list graph")
    listed = [e for e in res.get("errors", [])
              if e.get("node") == "impl" and e.get("field") == "context"]
    check(len(listed) == 1, "errors[] carries the named-node {node, field, msg} record")
    check(not runs.exists() or list(runs.iterdir()) == [],
          "REJECT WRITES ZERO RUN DIRS (WF_RUNS_ROOT untouched)")
    check(spawn_pings == [], "REJECT SPAWNS NOTHING")
    # ra-59 review finding 1/2 door rows: each falsy/null case the first candidate
    # accepted (fan-out prefix goals [] {} 0 False, explicit-null agent/gate context
    # and gate question) must refuse at the door AND create zero run dirs.
    for label, node in (
            ("falsy fan-out prefix goal []",
             {"id": "f", "type": "agent", "goal": [],
              "fanout": {"items": [{"goal": "work"}]}}),
            ("falsy fan-out prefix goal {}",
             {"id": "f", "type": "agent", "goal": {},
              "fanout": {"items": [{"goal": "work"}]}}),
            ("falsy fan-out prefix goal 0",
             {"id": "f", "type": "agent", "goal": 0,
              "fanout": {"items": [{"goal": "work"}]}}),
            ("falsy fan-out prefix goal False",
             {"id": "f", "type": "agent", "goal": False,
              "fanout": {"items": [{"goal": "work"}]}}),
            ("explicit-null agent context",
             {"id": "a", "type": "agent", "goal": "work", "context": None}),
            ("explicit-null gate context",
             {"id": "a", "type": "gate", "context": None}),
            ("explicit-null gate question",
             {"id": "a", "type": "gate", "question": None})):
        res = door.act_run({"graph": {"name": "wf59-probe",
                                      "nodes": [json.loads(json.dumps(node))]}})
        check(res.get("error", "").startswith("graph invalid:"),
              f"door rejects {label}")
        field = "goal" if "fan-out" in label else ("context" if "context" in label
                                                   else "question")
        check(any(e.get("node") == node["id"] and e.get("field") == field
                  for e in res.get("errors", [])),
              f"door errors[] names {node['id']}/{field} for {label}")
        check(not runs.exists() or list(runs.iterdir()) == [],
              f"{label}: door reject still writes ZERO run dirs")
    check(spawn_pings == [], "no probe ever spawned a runner")
    good = {"name": "typehole-59-ok",
            "nodes": [{"id": "impl", "type": "agent", "goal": "work",
                       "context": "preamble"}]}   # unpinned: seat default, like the door tests
    res = door.act_run({"graph": json.loads(json.dumps(good))})
    check("run_id" in res, "the well-typed control graph still launches")
    check(runs.is_dir() and any(d.is_dir() for d in runs.iterdir()),
          "control run dir exists")
finally:
    spawn.stop(); env.stop(); tmp.cleanup()

print(f"\nALL PASS ({ok})")
