#!/usr/bin/env python3
"""Door wiring for composite graphs (include-by-expansion, design 2026-09-30).

Hermetic (fake launcher, sandboxed HOME, fake seat via WF_RUNS_ROOT — the same
import convention as tests/test_library.py). Covers the door lane of the design:
 - D1 run with include expands BEFORE validation: on-disk graph.json carries the
   alias__id nodes and NO include key; run.json records includes provenance.
 - D2 unknown `use` -> ok:false envelope (errors[{node:'include:<alias>',...}])
   and NO run dir created.
 - D3 alias collision (alias__id vs a parent id) refused with a named error.
 - D4 dry_run honors include side-effect-free (lint expands, nothing written).
 - D5 amend of an include-expanded run is an identity no-op: graph.json
   round-trips unchanged (strip-on-expand => no include key on the expanded form).
 - D6 save stores the AUTHOR form (include key on disk) while validating the
   guards (unknown use refuses the save; valid composite shelves unre-expanded).
 - D7 WORKFLOW_PARAMS graph description mentions include (validator-caps pattern).
 - D8 run.json carries includes provenance AND include_notes on a shared fixed
   scratch-path fixture; status surfaces the notes.
 - D10 save(run_id) of a composite run refuses (its graph.json is the expanded
   form); plain-run save(run_id) keeps working.
 - D11 author-form amend restamps run.json includes/include_notes (never the
   previous graph's provenance); expanded-form amend leaves the stamp untouched.
 - D12 hyphenated alias refuses with the named include envelope at the door
   (never a downstream when-syntax error).
 - D13 child model_policy.forbidden_models unions into the expanded graph.json
   and the merge is noted in run.json include_notes.
 - D14 expansion and provenance read each shelf entry ONCE (memoized reader: a
   shelf mutated between the passes can never stamp a digest of other bytes).
 - D19 gate options[] and wait.until_argv[] join the seed-render/survivor
   surface: unseeded refuses, seeded RENDERS into the committed bytes (the old
   nested write-back only knew fanout), shelf bytes immutable, include-free
   gate bytes keep verbatim leniency.
"""
import importlib.util, json, os, shutil, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = Path(tempfile.mkdtemp(prefix="wf-include-door-"))
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "runs")           # fake seat (test_library pattern)
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "tests" / "fake")
spec = importlib.util.spec_from_file_location("hw_door_include", BUILD / "__init__.py")
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)
# #71: WF_RUNS_ROOT alone is not a sandbox — pin the settings door too (S3 audit).
sys.path.insert(0, str(HERE))
import wf_test_isolation as _iso71
_iso71.install(hw)

ok = True
_nchecks = 0
def check(label, cond, detail=""):
    global ok, _nchecks
    _nchecks += 1
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def call(**a):
    return json.loads(hw.handle(a))

ROOT = Path(os.environ["WF_RUNS_ROOT"])
def dirs():
    return set(p.name for p in ROOT.glob("*")) if ROOT.exists() else set()

# Library fixture: two tiny echo-only graphs. `revlib` carries a {run.VERDICT}
# seed slot; `scratchlib` shares a fixed absolute path with the parent fixture.
LIB = ROOT / "library"
LIB.mkdir(parents=True, exist_ok=True)
(LIB / "revlib.json").write_text(json.dumps({
    "name": "revlib", "nodes": [
        {"id": "look", "type": "echo", "output": "looked"},
        {"id": "v", "type": "agent", "after": ["look"], "goal": "JSON:{\"verdict\": \"{run.VERDICT}\"}"}]}))
(LIB / "scratchlib.json").write_text(json.dumps({
    "name": "scratchlib", "nodes": [
        {"id": "work", "type": "agent", "goal": "work in /tmp/wf-inc-shared keep {run.VERDICT}"}]}))

# ---------- D1: run with include expands before validation -------------------
meta = {"name": "d1", "include": [
    {"as": "rev", "use": "revlib", "seeds": {"VERDICT": "ship"}}],
    "nodes": [{"id": "join", "type": "agent", "after": ["rev__v"], "goal": "read rev__v"}]}
r = call(action="run", graph=meta)
rid = r.get("run_id")
check("D1 run with include launches", bool(rid), json.dumps(r))
g = json.loads((ROOT / rid / "graph.json").read_text())
ids = {n["id"] for n in g["nodes"]}
check("D1 graph.json has namespaced nodes", {"rev__look", "rev__v", "join"} <= ids, sorted(ids))
check("D1 graph.json has NO include key (strip-on-expand)", "include" not in g, sorted(g))
check("D1 seed rendered inside subtree",
      json.loads((ROOT / rid / "graph.json").read_text())
      and any(n["id"] == "rev__v" and "ship" in n["goal"] for n in g["nodes"]))
run_meta = json.loads((ROOT / rid / "run.json").read_text())
check("D1 run.json records includes provenance",
      run_meta.get("includes") == [{"alias": "rev", "name": "revlib",
                                    "source_digest": hw._common.source_digest(
                                        json.loads((LIB / "revlib.json").read_text()))}],
      json.dumps(run_meta.get("includes")))
st = call(action="wait", run_id=rid, timeout=60)
check("D1 expanded run reaches done", st.get("status") == "done", json.dumps(st.get("status")))
call(action="stop", run_id=rid)

# ---------- D2: unknown use -> envelope, no run dir ---------------------------
before = dirs()
r = call(action="run", graph={"name": "d2", "include": [
    {"as": "x", "use": "nope-missing"}], "nodes": [{"id": "a", "type": "echo", "output": "1"}]})
after = dirs()
rows = r.get("errors") or []
check("D2 unknown use refuses", "error" in r and not r.get("run_id"), json.dumps(r))
check("D2 envelope names include:<alias> with node/field/msg keys",
      any(e.get("node") == "include:x" and e.get("field") == "include"
          and set(e) >= {"node", "field", "msg"} for e in rows), json.dumps(r))
check("D2 no run dir created", before == after, (sorted(before), sorted(after)))

# ---------- D3: alias collision refused ----------------------------------------
collide = {"name": "d3", "include": [{"as": "rev", "use": "revlib", "seeds": {"VERDICT": "no"}}],
           "nodes": [{"id": "rev__look", "type": "echo", "output": "shadow"}]}
before = dirs()
r = call(action="run", graph=collide)
check("D3 collision refused with named error",
      "error" in r and any(str(e.get("node", "")).startswith("include:rev") for e in r.get("errors", [])),
      json.dumps(r))
check("D3 collision left no run dir", before == dirs())
# two includes sharing one alias
dup = {"name": "d3b", "include": [{"as": "rev", "use": "revlib", "seeds": {"VERDICT": "a"}},
                                  {"as": "rev", "use": "revlib", "seeds": {"VERDICT": "b"}}],
       "nodes": [{"id": "a", "type": "echo", "output": "1"}]}
r = call(action="run", graph=dup)
check("D3b duplicate alias refused",
      "error" in r and "duplicate alias" in json.dumps(r), json.dumps(r))

# ---------- D4: dry_run honors include, side-effect-free -----------------------
before = dirs()
lint = {"name": "d4", "include": [{"as": "rev", "use": "revlib", "seeds": {"VERDICT": "go"}}],
        "nodes": [{"id": "join", "type": "agent", "after": ["rev__v"], "goal": "j"}]}
r = call(action="run", graph=lint, dry_run=True)
check("D4 dry_run ok on a composite", r.get("ok") and r.get("dry_run"), json.dumps(r))
check("D4 dry_run wrote nothing", before == dirs(), (sorted(before), sorted(dirs())))
r = call(action="run", graph={"name": "d4b", "include": [{"as": "x", "use": "nope"}],
                              "nodes": [{"id": "a", "type": "echo", "output": "1"}]}, dry_run=True)
check("D4b dry_run refuses a bad include + wrote nothing",
      "error" in r and before == dirs(), json.dumps(r))

# ---------- D5: amend on the expanded run is identity-stable ------------------
path = ROOT / rid / "graph.json"
before_bytes = path.read_bytes()
r = call(action="amend", run_id=rid, graph=g, dry_run=True)
check("D5 amend dry_run ok on the expanded form (no include key present)",
      r.get("ok") and r.get("dry_run"), json.dumps(r))
r = call(action="amend", run_id=rid, graph=g)
check("D5 amend applies on the expanded form", r.get("ok"), json.dumps(r))
after_bytes = path.read_bytes()
check("D5 graph.json round-trips unchanged (strip-on-expand identity no-op)",
      json.loads(before_bytes) == json.loads(after_bytes))
# amends.jsonl recorded the same old/new graph (expansion changed nothing)
am = [json.loads(l) for l in (ROOT / rid / "amends.jsonl").read_text().splitlines()]
check("D5 amend record old==new (expanded form carries no include)",
      am[-1]["old"] == am[-1]["new"] and "include" not in am[-1]["new"])
# a replacement graph WITH an unknown include refuses BEFORE the replace
before_bytes2 = path.read_bytes()
r = call(action="amend", run_id=rid,
         graph={"name": "d5bad", "include": [{"as": "z", "use": "nope"}],
                "nodes": [{"id": "a", "type": "echo", "output": "1"}]})
check("D5b amend with unknown include refuses", "error" in r and not r.get("ok"), json.dumps(r))
check("D5b refused amend left graph.json bytes untouched",
      path.read_bytes() == before_bytes2)

# ---------- D6: save stores the author form, guards validated ------------------
author = {"name": "d6-composite", "include": [
    {"as": "rev", "use": "revlib", "seeds": {"VERDICT": "ship"}}],
    "nodes": [{"id": "join", "type": "agent", "after": ["rev__v"], "goal": "join"}]}
r = call(action="save", graph=author, name="d6-composite")
check("D6 save accepts a valid composite", r.get("saved") == "d6-composite", json.dumps(r))
shelved = json.loads((LIB / "d6-composite.json").read_text())
check("D6 shelf keeps the AUTHOR form WITH the include key (un-expanded)",
      shelved.get("include") == author["include"]
      and {n["id"] for n in shelved["nodes"]} == {"join"}, json.dumps(shelved))
# guard at save time: unknown use refuses, nothing written
bad_shelf = LIB / "d6-bad.json"
r = call(action="save", graph={"name": "d6-bad", "include": [{"as": "q", "use": "ghost"}],
                               "nodes": [{"id": "a", "type": "echo", "output": "1"}]}, name="d6-bad")
check("D6b save validates guards: unknown use refused", "error" in r, json.dumps(r))
check("D6b refused save wrote nothing", not bad_shelf.exists())
# a shelved composite replays through from= and expands at run time
r = call(action="run", **{"from": "d6-composite"})
rid2 = r.get("run_id")
check("D6c run from= of a shelved composite expands at run time", bool(rid2), json.dumps(r))
g2 = json.loads((ROOT / rid2 / "graph.json").read_text())
check("D6c replayed graph.json is expanded + stripped",
      "include" not in g2 and any(n["id"] == "rev__v" for n in g2["nodes"]), sorted(g2))
check("D6c replay records provenance", bool(
    json.loads((ROOT / rid2 / "run.json").read_text()).get("includes")))
call(action="stop", run_id=rid2)
# plain-save bytes unchanged: no include key involved, the 1.0 key set stands
r = call(action="save", graph={"name": "plain-d6", "nodes": [{"id": "a", "type": "echo", "output": "1"}]},
         name="plain-d6")
check("D6d plain save untouched (no include in the shelved bytes)",
      "include" not in json.loads((LIB / "plain-d6.json").read_text()))

# ---------- D7: WORKFLOW_PARAMS description mentions include -------------------
desc = hw.WORKFLOW_PARAMS["properties"]["graph"]["description"]
check("D7 schema description documents include",
      "`include:[{as, use, seeds?, exports?}]`" in desc
      and "alias__<id>" in desc and "include_notes" in desc, desc[:150])
check("D7 the caps-pin closer is kept verbatim",
      desc.endswith("Any key outside these closed sets is rejected at run/amend with "
                    "errors:[{node, field, msg}] for EVERY defect."))
# F-6 (review): a runtime schema-surface assertion, not an implementation-text/
# line-width grep. What the schema must guarantee is that the AGENT-VISIBLE surface
# (the parameter schema itself, whatever its source lines look like) fully names the
# composite contract: directive keys, namespacing, the strip-on-expand storage law,
# the save(run_id) exception, and the shared error envelope.
check("D7 the runtime graph schema names the whole composite contract",
      all(f in desc for f in ("`include:[{as, use, seeds?, exports?}]`", "alias__<id>",
                              "include-STRIPPED", "save(run_id)", "include_notes",
                              "errors:[{node:'include:<alias>', field, msg}]")),
      "missing a contract surface in the schema description")

# ---------- D8: provenance + include_notes on a shared-path fixture ------------
meta2 = {"name": "d8", "include": [
    {"as": "rev", "use": "revlib", "seeds": {"VERDICT": "ship"}},
    {"as": "scr", "use": "scratchlib", "seeds": {"VERDICT": "x"}}],
    "nodes": [{"id": "prep", "type": "agent", "goal": "stage at /tmp/wf-inc-shared"},
              {"id": "join", "type": "agent", "after": ["rev__v", "scr__work"], "goal": "j"}]}
r = call(action="run", graph=meta2)
rid3 = r.get("run_id")
check("D8 shared-path composite launches (notes are non-fatal)", bool(rid3), json.dumps(r))
check("D8 launch response surfaces include_notes",
      any("fixed path" in n and "scr" in n for n in r.get("include_notes", [])),
      json.dumps(r.get("include_notes")))
m3 = json.loads((ROOT / rid3 / "run.json").read_text())
check("D8 run.json includes[] in declaration order with digests",
      [i["alias"] for i in m3.get("includes", [])] == ["rev", "scr"]
      and all(i.get("source_digest") for i in m3["includes"]), json.dumps(m3.get("includes")))
check("D8 run.json carries include_notes", bool(m3.get("include_notes")), json.dumps(m3.get("include_notes")))
st = call(action="status", run_id=rid3)
check("D8 status surfaces include_notes", bool(st.get("include_notes")), json.dumps(st.get("include_notes")))
call(action="stop", run_id=rid3)
# a plain run keeps the pre-include run.json key set (empty provenance omitted)
r = call(action="run", graph={"name": "d8-plain", "nodes": [{"id": "a", "type": "echo", "output": "1"}]})
m4 = json.loads((ROOT / r["run_id"] / "run.json").read_text())
check("D8b plain run.json carries neither includes nor include_notes",
      "includes" not in m4 and "include_notes" not in m4, json.dumps(sorted(m4)))
call(action="stop", run_id=r["run_id"])

# ---------- D9: unbound include refs are fail-closed (live receipt 2026-09-30) --
# subtree {run.KEY} surviving include seeds AND run_context binding must refuse
# BEFORE any write/spawn; parent-authored leniency (seed-less literal spawns) and
# run_context-covering-the-subtree both stay allowed.
r = call(action="run", graph={"name": "d9-noseeds", "include": [{"as": "rev", "use": "revlib"}],
                              "nodes": [{"id": "p", "type": "echo", "output": "1"}]})
check("D9 include subtree with unbound {run.KEY} and no seeds/run_context refuses",
      r.get("ok") is not True and "unbound" in json.dumps(r) and not r.get("run_id"),
      json.dumps(r)[:200])
r = call(action="run", graph={"name": "d9-miss", "include": [{"as": "rev", "use": "revlib", "seeds": {"OTHER": "x"}}],
                              "nodes": [{"id": "p", "type": "echo", "output": "1"}]},
         run_context={"VERDICT": "from-ctx"})
# A declared seeds map is a CLOSED contract (resolver refuses VERDICT-absent even
# when run_context covers it — seeds present means the include owns the subtree
# contract). The run_context path is the NO-seeds key form:
r2 = r
check("D9b2 declared seeds map stays closed over run_context",
      "unbound" in json.dumps(r2), json.dumps(r2)[:160])
r = call(action="run", graph={"name": "d9-ctx", "include": [{"as": "rev", "use": "revlib"}],
                              "nodes": [{"id": "p", "type": "echo", "output": "1"}]},
         run_context={"VERDICT": "from-ctx"})
check("D9 include without seeds binds subtree refs from run_context (launches)",
      bool(r.get("run_id")), json.dumps(r)[:200])
if r.get("run_id"):
    call(action="stop", run_id=r["run_id"])
# seed map wins inside the subtree; parent literal-spawn leniency untouched
r = call(action="run", graph={"name": "d9-lenient",
                              "nodes": [{"id": "a", "type": "agent", "goal": "say {run.NOTHING}"}]})
check("D9b parent node with unbound ref keeps plain-graph leniency",
      bool(r.get("run_id")), json.dumps(r)[:120])
if r.get("run_id"):
    call(action="stop", run_id=r["run_id"])

# ---------- D10: save(run_id) of a composite run REFUSES (C6) -------------------
# the composite run's graph.json is the expanded, include-STRIPPED form; shelving
# it would freeze one expansion of the shelf (author-form contract). Plain runs
# keep the pre-include save(run_id) behavior.
r = call(action="save", run_id=rid, name="d10-frozen")   # rid = D1 composite run
check("D10 save(run_id) of a composite run refuses",
      "error" in r and "include" in json.dumps(r).lower(), json.dumps(r))
check("D10 refusal wrote no shelf", not (LIB / "d10-frozen.json").exists())
rp = call(action="run", graph={"name": "d10-plain",
                               "nodes": [{"id": "a", "type": "echo", "output": "1"}]})
r = call(action="save", run_id=rp["run_id"], name="d10-plain")
check("D10b save(run_id) of a PLAIN run still works", r.get("saved") == "d10-plain",
      json.dumps(r))
call(action="stop", run_id=rp["run_id"])

# ---------- D11: author-form amend restamps run.json provenance (C5) -----------
# after the D1 run (includes alias 'rev'), amend with a FRESH author form under a
# new alias + a shared-path node: run.json includes/include_notes must describe
# the NEW graph, never the previous one.
amend_graph = {"name": "d1", "include": [
    {"as": "rev9", "use": "scratchlib", "seeds": {"VERDICT": "x"}}],
    "nodes": [{"id": "prep", "type": "agent", "goal": "stage at /tmp/wf-inc-shared"}]}
r = call(action="amend", run_id=rid, graph=amend_graph)
check("D11 author-form amend applies", r.get("ok"), json.dumps(r)[:200])
m = json.loads((ROOT / rid / "run.json").read_text())
check("D11 run.json includes restamped to the amended author form",
      [i["alias"] for i in m.get("includes", [])] == ["rev9"]
      and m["includes"][0]["name"] == "scratchlib", json.dumps(m.get("includes")))
check("D11 run.json include_notes restamped (shared-path note for the new graph)",
      any("scr9" in n or "rev9" in n for n in m.get("include_notes", [])),
      json.dumps(m.get("include_notes")))
g = json.loads((ROOT / rid / "graph.json").read_text())
check("D11 amended graph.json is the new expanded form",
      "include" not in g and any(n["id"] == "rev9__work" for n in g["nodes"]),
      sorted(n["id"] for n in g["nodes"]))
# an expanded-form amend (no include key) leaves the last author-form stamp intact
r = call(action="amend", run_id=rid, graph=g)
m2 = json.loads((ROOT / rid / "run.json").read_text())
check("D11b expanded-form amend leaves the include stamp untouched",
      m2.get("includes") == m.get("includes"), json.dumps(m2.get("includes")))
call(action="stop", run_id=rid)

# ---------- D12: hyphenated alias refuses at the door with the named envelope ---
before = dirs()
r = call(action="run", graph={"name": "d12", "include": [
    {"as": "my-rev", "use": "revlib", "seeds": {"VERDICT": "go"}}],
    "nodes": [{"id": "a", "type": "echo", "output": "1"}]})
check("D12 hyphenated alias -> named include-guard refusal (not a when-syntax error)",
      "error" in r and "invalid alias" in json.dumps(r) and "bad char" not in json.dumps(r),
      json.dumps(r)[:250])
check("D12 refusal names include:<alias> in the envelope",
      any(str(e.get("node", "")).startswith("include:my-rev") for e in r.get("errors", [])),
      json.dumps(r)[:250])
check("D12 no run dir created", before == dirs())

# ---------- D13: child model_policy survives to the committed expanded graph ----
(LIB / "pollib.json").write_text(json.dumps({
    "name": "pollib", "model_policy": {"forbidden_models": ["bad-shelf-model"]},
    "nodes": [{"id": "w", "type": "echo", "output": "1"}]}))
r = call(action="run", graph={"name": "d13", "include": [{"as": "p", "use": "pollib"}],
                              "nodes": [{"id": "a", "type": "echo", "output": "1"}]})
rid5 = r.get("run_id")
check("D13 policy-bearing include launches", bool(rid5), json.dumps(r)[:200])
g3 = json.loads((ROOT / rid5 / "graph.json").read_text())
check("D13 expanded graph.json carries the unioned forbidden_models floor",
      g3.get("model_policy", {}).get("forbidden_models") == ["bad-shelf-model"],
      json.dumps(g3.get("model_policy")))
m3b = json.loads((ROOT / rid5 / "run.json").read_text())
check("D13 merge recorded in include_notes",
      any("model_policy.forbidden_models merged" in n for n in m3b.get("include_notes", [])),
      json.dumps(m3b.get("include_notes")))
call(action="stop", run_id=rid5)

# ---------- D14: expansion + provenance read each shelf entry ONCE (C4) --------
_orig_lr = hw._library_reader
_reads = []
def _counting_lr():
    base = _orig_lr()
    def read(name):
        _reads.append(name)
        return base(name)
    return read
hw._library_reader = _counting_lr
try:
    exp14, notes14, prov14, bad14 = hw._expand_includes_at_door(
        {"name": "d14", "include": [{"as": "p", "use": "pollib"}],
         "nodes": [{"id": "a", "type": "echo", "output": "1"}]})
    check("D14 memoized door reader: one library read per name per call",
          bad14 is None and _reads == ["pollib"], f"reads={_reads}")
finally:
    hw._library_reader = _orig_lr

# ---------- D15: direct-vs-include differential validation (PR#84 review F-2) ---
# A graph that direct submission REFUSES must be refused through the include door
# too — same strictness, named include envelope, zero run dirs. The shelf is now
# measured with the shared full validator (structural + node) before any lossy
# top-level projection or policy merge touches it.
for _label, _patch in [("unknown graph key", {"typo_key": 1}),
                       ("bad defaults", {"defaults": {"timeout": -1}}),
                       ("bad policy", {"model_policy": {"require_model": 0}}),
                       ("bad provenance", {"provenance": {"unknown": 1}})]:
    (LIB / "d15child.json").write_text(json.dumps(
        {"name": "d15child", "nodes": [{"id": "s", "type": "echo", "output": "ok"}],
         **_patch}))
    before = dirs()
    r = call(action="run", graph={"name": "d15", "include": [{"as": "x", "use": "d15child"}],
                                  "nodes": [{"id": "p", "type": "echo", "output": "1"}]})
    check(f"D15 {_label}: direct submission refuses",
          bool(call(action="run", dry_run=True, graph=json.loads(
              (LIB / "d15child.json").read_text())).get("errors")))
    check(f"D15 {_label}: include refuses with the named envelope",
          "error" in r and any(str(e.get("node", "")).startswith("include:x")
                               for e in r.get("errors", [])), json.dumps(r)[:160])
    check(f"D15 {_label}: no run dir", before == dirs())
# a malformed NODE id in the child: the old node-only checker TypeErrors on
# set(ids) BEFORE normalizing; the full validator normalizes first and the door
# must answer with the errors envelope, never a trace.
(LIB / "d15child.json").write_text(json.dumps(
    {"name": "d15child", "nodes": [{"id": ["bad"], "type": "echo", "output": "ok"}]}))
before = dirs()
r = call(action="run", graph={"name": "d15", "include": [{"as": "x", "use": "d15child"}],
                              "nodes": [{"id": "p", "type": "echo", "output": "1"}]})
check("D15 malformed child id envelope: errors rows, no TypeError trace",
      "error" in r and "Traceback" not in json.dumps(r)
      and "TypeError" not in json.dumps(r)
      and any(str(e.get("node", "")).startswith("include:x") for e in r.get("errors", [])),
      json.dumps(r)[:200])
check("D15 malformed child id: no run dir", before == dirs())
# Issue #192 D15-SIBLING: malformed PARENT id + valid include -> the named errors[]
# envelope, never a TypeError trace (the parent_ids set build used to crash first).
(LIB / "okchild.json").write_text(json.dumps(
    {"name": "okchild", "nodes": [{"id": "s", "type": "echo", "output": "ok"}]}))
before = dirs()
r = call(action="run", graph={"name": "d15parent", "include": [{"as": "x", "use": "okchild"}],
                              "nodes": [{"id": ["bad"], "type": "echo", "output": "1"}]})
check("D15-sib malformed parent id envelope: errors rows, no TypeError trace",
      "error" in r and "Traceback" not in json.dumps(r)
      and "TypeError" not in json.dumps(r)
      and any("malformed parent node id" in str(e.get("msg", "")) for e in r.get("errors", [])),
      json.dumps(r)[:200])
check("D15-sib malformed parent id: no run dir", before == dirs())
# a MALFORMED PARENT require_model must not be repaired by the policy merge
# ('false' is truthy -> the old OR wrote boolean True and passed; direct
# submission refuses the same string).
(LIB / "d15child.json").write_text(json.dumps(
    {"name": "d15child", "model_policy": {"forbidden_models": ["m-x"]},
     "nodes": [{"id": "s", "type": "echo", "output": "ok"}]}))
before = dirs()
r = call(action="run", dry_run=True, graph={"name": "d15p",
              "include": [{"as": "x", "use": "d15child"}],
              "model_policy": {"require_model": "false"},
              "nodes": [{"id": "p", "type": "echo", "output": "1"}]})
check("D15 malformed parent require_model refused pre-merge (no silent True)",
      bool(r.get("errors")) and "require_model" in json.dumps(r), json.dumps(r)[:200])
check("D15 malformed parent policy: no run dir", before == dirs())
r = call(action="run", dry_run=True, graph={"name": "d15q",
              "include": [{"as": "x", "use": "d15child"}],
              "model_policy": {"require_model": 0},
              "nodes": [{"id": "p", "type": "echo", "output": "1"}]})
check("D15 int require_model:0 refused too (no truthy coercion either way)",
      bool(r.get("errors")) and "require_model" in json.dumps(r), json.dumps(r)[:200])

# ---------- D16: echo output joins the seed/survivor surface (PR#84 F-3) --------
# An included echo's string output is rendered by include seeds, and a surviving
# {run.KEY} there is refused before any write (the runner commits echo output
# VERBATIM — a literal placeholder used to land as a done node's verdict).
(LIB / "echolib.json").write_text(json.dumps(
    {"name": "echolib", "nodes": [
        {"id": "s", "type": "echo", "output": "verdict={run.MISSING}"}]}))
seeded = {"name": "d16", "include": [{"as": "x", "use": "echolib",
                                      "seeds": {"OTHER": "v"}}],
          "nodes": [{"id": "p", "type": "echo", "output": "1"}]}
before = dirs()
r = call(action="run", graph=seeded, run_context={"OTHER": "v"})
check("D16 unbound echo-output ref refuses the run (no write, no done placeholder)",
      "error" in r and "run.MISSING" in json.dumps(r) and before == dirs(),
      json.dumps(r)[:200])
r = call(action="run", graph={"name": "d16b", "include": [{"as": "x", "use": "echolib",
                                                          "seeds": {"MISSING": "ship"}}],
                              "nodes": [{"id": "p", "type": "echo", "output": "1"}]})
check("D16 seed covers the echo surface (the SAME ref renders clean)",
      bool(r.get("run_id")), json.dumps(r)[:160])
if r.get("run_id"):
    w = call(action="wait", run_id=r["run_id"], timeout=60)
    n = json.loads((ROOT / r["run_id"] / "nodes" / "x__s.json").read_text())
    check("D16 seeded echo commits the rendered output",
          w.get("status") == "done" and n.get("output") == "verdict=ship",
          json.dumps(n)[:160])
    call(action="stop", run_id=r["run_id"])
# include-free echo bytes stay verbatim (the golden law): a {run.X} in a PLAIN
# graph's echo output is NOT refused — plain-graph leniency is untouched.
r = call(action="run", graph={"name": "d16-lenient", "nodes": [
    {"id": "a", "type": "echo", "output": "say {run.NOTHING}"}]})
check("D16b include-free echo output keeps verbatim leniency (golden bytes)",
      bool(r.get("run_id")), json.dumps(r)[:120])
if r.get("run_id"):
    w = call(action="wait", run_id=r["run_id"], timeout=60)
    n = json.loads((ROOT / r["run_id"] / "nodes" / "a.json").read_text())
    check("D16b plain echo output committed byte-verbatim",
          n.get("output") == "say {run.NOTHING}", json.dumps(n)[:160])
    call(action="stop", run_id=r["run_id"])

# ---------- D17: export collisions are order-independent (PR#84 review F-4) ----
(LIB / "alpha.json").write_text(json.dumps(
    {"name": "alpha", "nodes": [{"id": "s", "type": "echo", "output": {"verdict": "ship"}}]}))
(LIB / "beta.json").write_text(json.dumps(
    {"name": "beta", "nodes": [{"id": "s", "type": "echo", "output": {"verdict": "hold"}}]}))
a_dir = {"as": "a", "use": "alpha", "exports": {"s": "b__s"}}
b_dir = {"as": "b", "use": "beta"}
# every parent ref surface that could silently resolve the shadowed name
surfaces = {
    "after": [{"id": "judge", "type": "echo", "after": ["b__s"], "output": "j"}],
    "when": [{"id": "judge", "type": "gate", "after": ["beta__s"], "question": "q",
              "when": "out.b__s.verdict == 'ship'"}],
    "inputs": [{"id": "judge", "type": "echo", "after": ["beta__s"], "output": "j",
                "inputs": ["b__s.verdict"]}],
}
for sname, pnodes in surfaces.items():
    for order in ([a_dir, b_dir], [b_dir, a_dir]):
        r = call(action="run", dry_run=True,
                 graph={"name": "d17", "include": list(order), "nodes": pnodes})
        check(f"D17 {sname} surface, order {[d['as'] for d in order]}: refused",
              "error" in r and "shadows" in json.dumps(r), json.dumps(r)[:180])

# ---------- D18: author-form amend DROPS stale include_notes (PR#84 F-5) --------
# first composite: an include whose fixed scratch path shares the parent's ->
# warnings persist. Replacement author form: a CLEAN include, no warnings. After
# the amend, run.json AND status must stop naming the old graph's path.
(LIB / "oldscratch.json").write_text(json.dumps(
    {"name": "oldscratch", "nodes": [
        {"id": "w", "type": "agent", "goal": "use /tmp/wf-inc-stale"}]}))
_orig_spawn = hw._spawn_runner
hw._spawn_runner = lambda r: 0        # persistence-only: nothing is launched
try:
    r = call(action="run", graph={"name": "d18",
                                  "include": [{"as": "old", "use": "oldscratch"}],
                                  "nodes": [{"id": "p", "type": "agent",
                                             "goal": "use /tmp/wf-inc-stale"}]})
    rid18 = r.get("run_id")
    check("D18 warning-bearing composite launches with notes",
          bool(rid18) and any("fixed path" in n for n in r.get("include_notes", [])),
          json.dumps(r)[:160])
    m = json.loads((ROOT / rid18 / "run.json").read_text())
    check("D18 run.json carries the stale-capable notes",
          any("old" in n for n in m.get("include_notes", [])), json.dumps(m)[:160])
    r2 = call(action="amend", run_id=rid18, graph={"name": "d18",
                  "include": [{"as": "new", "use": "revlib", "seeds": {"VERDICT": "go"}}],
                  "nodes": [{"id": "p", "type": "echo", "output": "clean"}]})
    check("D18 clean-include amend succeeds", r2.get("ok"), json.dumps(r2)[:160])
    m2 = json.loads((ROOT / rid18 / "run.json").read_text())
    check("D18 warning -> no-warning persistence: notes cleared, not inherited",
          "include_notes" not in m2
          and [i["alias"] for i in m2.get("includes", [])] == ["new"],
          json.dumps(m2)[:200])
    st = call(action="status", run_id=rid18)
    check("D18 status no longer surfaces the old warning",
          not st.get("include_notes"), json.dumps(st.get("include_notes")))
    # expanded-form amend still leaves the (now absent) stamp untouched
    g18 = json.loads((ROOT / rid18 / "graph.json").read_text())
    call(action="amend", run_id=rid18, graph=g18)
    m3 = json.loads((ROOT / rid18 / "run.json").read_text())
    check("D18 expanded-form amend keeps the no-op (no notes reappear)",
          "include_notes" not in m3 and m3.get("includes") == m2.get("includes"),
          json.dumps(m3)[:200])
finally:
    hw._spawn_runner = _orig_spawn

# ---------- D19: gate options[] + wait.until_argv[] join the surface (PR#84 round-2 P1)
# Same class as D16/echo: `options` surface VERBATIM on the human release card and
# `until_argv` is exec'd as fixed argv. An included gate's options/argv must (a)
# refuse an unseeded {run.KEY} through the errors envelope and (b) actually RENDER
# a seeded value — the old nested write-back assumed every nested field was
# `fanout`, so even a supplied seed left both literals committed untouched.
(LIB / "gatelib.json").write_text(json.dumps({
    "name": "gatelib", "nodes": [
        {"id": "g", "type": "gate", "question": "Question {run.Q}",
         "options": ["yes {run.OPTION}", "no"],
         "wait": {"until_argv": ["true", "{run.OPTION}"]}}]}))
_d19_comp = {"name": "d19", "include": [{"as": "gx", "use": "gatelib"}],
             "nodes": [{"id": "p", "type": "agent", "after": ["gx__g"], "goal": "read gx__g"}]}
before = dirs()
r = call(action="run", graph={**_d19_comp,
                             "include": [{"as": "gx", "use": "gatelib",
                                          "seeds": {"Q": "rendered"}}]})
check("D19 unseeded OPTION in options/until_argv refuses (errors envelope, no run dir)",
      ("error" in r or "errors" in r) and "OPTION" in json.dumps(r) and before == dirs(),
      json.dumps(r)[:200])
r = call(action="run", dry_run=True, graph={**_d19_comp,
              "include": [{"as": "gx", "use": "gatelib", "seeds": {"Q": "rendered"}}]})
check("D19 dry_run refuses too (was ok:true with committed literals)",
      bool(r.get("errors") or "error" in r) and before == dirs(), json.dumps(r)[:200])
# seeded: the value must actually LAND in options and until_argv (the stronger
# adversary counterexample: supplying OPTION used to leave both literals in place)
shelf_bytes = (LIB / "gatelib.json").read_bytes()
_orig_spawn19 = hw._spawn_runner
hw._spawn_runner = lambda rr: 0        # persistence-only: graph.json is the artifact under test
try:
    r = call(action="run", graph={**_d19_comp,
                  "include": [{"as": "gx", "use": "gatelib",
                               "seeds": {"Q": "rendered", "OPTION": "bound"}}]})
    rid19 = r.get("run_id")
    check("D19 seeded composite launches", bool(rid19), json.dumps(r)[:160])
    if rid19:
        g19 = json.loads((ROOT / rid19 / "graph.json").read_text())
        n19 = next(n for n in g19["nodes"] if n["id"] == "gx__g")
        check("D19 seeded renders into options[] (committed bytes)",
              n19.get("options") == ["yes bound", "no"], json.dumps(n19)[:200])
        check("D19 seeded renders into wait.until_argv[] (committed bytes)",
              n19.get("wait", {}).get("until_argv") == ["true", "bound"],
              json.dumps(n19)[:200])
        check("D19 survivor sweep: committed graph carries no {run.*} in the subtree",
              hw._unbound_include_refs(g19, [{"alias": "gx"}]) is None
              and "{run." not in json.dumps(n19))
    check("D19 shelf file bytes immutable through render",
          (LIB / "gatelib.json").read_bytes() == shelf_bytes)
finally:
    hw._spawn_runner = _orig_spawn19
# include-free golden bytes: a PLAIN graph's gate keeps verbatim options/argv
# leniency (no include, no closed-seed contract — the pre-PR byte law).
r = call(action="run", graph={"name": "d19-plain", "nodes": [
    {"id": "g", "type": "gate", "question": "q {run.NOTHING}",
     "options": ["yes {run.NOTHING}", "no"]}]})
check("D19b include-free gate keeps verbatim leniency (golden bytes)",
      bool(r.get("run_id")), json.dumps(r)[:120])
if r.get("run_id"):
    g19p = json.loads((ROOT / r["run_id"] / "graph.json").read_text())
    n19p = next(n for n in g19p["nodes"] if n["id"] == "g")
    check("D19b plain gate options committed byte-verbatim",
          n19p.get("options") == ["yes {run.NOTHING}", "no"], json.dumps(n19p)[:160])
    call(action="stop", run_id=r["run_id"])

shutil.rmtree(HOME, ignore_errors=True)
print(f"{'ALL PASS' if ok else 'FAILURES PRESENT'} ({_nchecks} door contracts)")
sys.exit(0 if ok else 1)
