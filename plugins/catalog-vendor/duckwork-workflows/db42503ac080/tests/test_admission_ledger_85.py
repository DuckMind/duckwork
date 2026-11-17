#!/usr/bin/env python3
"""#85 — artifact-admission guard: input ledgers map 1:1 to declared sources.

The class (WOFS W1f evidence-loss): a fan-out item consumed an artifact another
item's source actually covered — a disposition ledger had silently lost rows and
nothing at admission could tell the runner. `fanout.ledger` is the item-indexed
INPUT LEDGER (one row per item, positionally aligned; a '<node_id>.<dotted.path>'
string or {source, artifact?:{file, sha256?}}). The guard
(wfcommon.admission_ledger_errors) refuses admission FAIL-CLOSED unless rows map
1:1 to items; the door composes it into _validation_error so every admission path
(run/amend/submit/save/validate) measures before any write/spawn, and wf.py
re-measures the bytes at runner start and hot-reload.

The validator/guard split is the pinned law (RED graph stays VALIDATOR-CLEAN):
  * container shape (non-list ledger) is the VALIDATOR's defect;
  * every other refusal — missing/extra row, shared source, non-ancestor head,
    malformed/artifact defects, missing run-dir bytes, sha mismatch — can only
    come from the GUARD.

RED-first proof, run in-process: the guard is neutralised (patched to a no-op),
the door then ADMITS the RED graph (an item whose ledger row is absent) — the
pre-#85 bug reproduced; with the guard live the identical graph is REFUSED.

Runnable two ways (repo convention): `python3 tests/test_admission_ledger_85.py`
prints PASS/FAIL lines, exit 0 = green; pytest can also collect it.
"""
import copy, hashlib, importlib.util, json, os, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-adv85"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
# #71: WF_RUNS_ROOT alone is not a sandbox — pin the resolver too, or saves
# ride the owner's settings.runs_root into the estate.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(HERE / "fake")
(HOME / "config.yaml").write_text("model:\n  default: seat-default\n")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import wfcommon  # noqa: E402
_spec = importlib.util.spec_from_file_location("door85", ROOT / "__init__.py")
door = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)

fails = 0
def check(cond, label, detail=""):
    global fails
    if cond:
        print("PASS", label)
    else:
        fails += 1
        print("FAIL", label, f" << {detail}" if detail else "")

def call(**a):
    return json.loads(door.handle(a)) if isinstance(door.handle(a), str) else door.handle(a)

# ---------------- fixtures ----------------
def agent(nid, **kw):
    return {"id": nid, "type": "agent", "goal": f"goal of {nid}", **kw}

def fan_graph(items, ledger, **fokw):
    """seed -> fan, fan.after=[seed]; ledger rows reference seed.facts[i]."""
    return {"name": "g85", "nodes": [
        agent("seed"),
        agent("fan", after=["seed"],
              fanout={"items": items, "goal": "process {item}", "ledger": ledger, **fokw}),
    ]}

ITEMS = [{"key": "k0"}, {"key": "k1"}, {"key": "k2"}]
ROWS = [f"seed.facts.{i}" for i in range(3)]
SHA = lambda b: hashlib.sha256(b).hexdigest()

# ---------------- (1) the split: validator vs guard ----------------
# validator-clean ledger rows (every refusal below must carry field fanout.ledger
# AND be validator-clean, proving the guard — not the validator — refuses).
clean = fan_graph(ITEMS, list(ROWS))
check(wfcommon.validate_graph_errors(clean["nodes"]) == [],
      "ledger is ACCEPTED by the closed-set validator (FANOUT_KEYS gained 'ledger')")
check(wfcommon.admission_ledger_errors(clean) == [],
      "1:1 string-row ledger passes the guard (no run dir needed)")

# container shape is the VALIDATOR's defect (guard skips it — no double-report)
bad_container = fan_graph(ITEMS, {"source": "seed.facts.0"})
vc = wfcommon.validate_graph_errors(bad_container["nodes"])
check(len(vc) == 1 and vc[0]["node"] == "fan" and vc[0]["field"] == "fanout.ledger",
      "non-list ledger is a VALIDATOR defect naming fanout.ledger", vc)
check(wfcommon.admission_ledger_errors(bad_container) == [],
      "guard skips a non-list ledger (container shape is the validator's)")

# ---------------- (2) the RED graph: VALIDATOR-CLEAN, guard-only refusal ----------------
red = fan_graph(ITEMS, ROWS[:2])                      # item 2 has no row
check(wfcommon.validate_graph_errors(red["nodes"]) == [],
      "RED graph (an item with no ledger row) is VALIDATOR-CLEAN",
      wfcommon.validate_graph_errors(red["nodes"]))
errs = wfcommon.admission_ledger_errors(red)
check(len(errs) == 1 and errs[0]["node"] == "fan" and errs[0]["field"] == "fanout.ledger"
      and "item 2" in errs[0]["msg"] and "missing ledger source" in errs[0]["msg"],
      "guard refuses the missing row NAMING the item", errs)

# RED-first control: neutralise the guard -> the door admits (the pre-#85 bug);
# restore -> the identical graph is refused. In-process, no reinstall needed.
_live = wfcommon.admission_ledger_errors
door_wired = getattr(door, "admission_ledger_errors", None)
try:
    wfcommon.admission_ledger_errors = lambda g, run_dir=None: []
    if door_wired is not None:
        door.admission_ledger_errors = wfcommon.admission_ledger_errors
    r = call(action="run", graph=copy.deepcopy(red))
    rid = r.get("run_id")
    check(bool(rid), "GUARD-OFF: door ADMITS the RED graph (pre-#85 bug reproduced)",
          json.dumps(r)[:300])
    if rid:
        call(action="stop", run_id=rid)
finally:
    wfcommon.admission_ledger_errors = _live
    if door_wired is not None:
        door.admission_ledger_errors = _live
r = call(action="run", graph=copy.deepcopy(red))
check("run_id" not in r and r.get("error")
      and any(e.get("field") == "fanout.ledger" for e in r.get("errors", [])),
      "GUARD-ON: the identical graph is REFUSED at admission (fail-closed, before write)",
      json.dumps(r)[:300])

# ---------------- (3) the rest of the 1:1 laws ----------------
def guard_errors(graph, run_dir=None):
    return wfcommon.admission_ledger_errors(graph, run_dir=run_dir)

# surplus row
e = guard_errors(fan_graph(ITEMS, ROWS + ["seed.facts.3"]))
check(len(e) == 1 and "row 3 has no item" in e[0]["msg"], "surplus ledger row refused", e)

# shared source (two items, one source)
e = guard_errors(fan_graph(ITEMS, ["seed.facts.0", "seed.facts.0", "seed.facts.1"]))
check(len(e) == 1 and "item 1" in e[0]["msg"] and "already declared" in e[0]["msg"],
      "two items sharing one source refused, naming the second item", e)

# source head outside the after ancestry
e = guard_errors({"name": "g85b", "nodes": [
    agent("seed"), agent("elsewhere"),
    agent("fan", after=["seed"], fanout={"items": ITEMS[:1], "goal": "x {item}",
                                         "ledger": ["elsewhere.facts.0"]}),
]})
check(len(e) == 1 and "not an ancestor" in e[0]["msg"], "non-ancestor source head refused", e)

# transitive ancestry is allowed (direct law is 'after ancestry', not direct-only)
e = guard_errors({"name": "g85c", "nodes": [
    agent("root"), agent("mid", after=["root"]),
    agent("fan", after=["mid"], fanout={"items": ITEMS[:1], "goal": "x {item}",
                                        "ledger": ["root.facts.0"]}),
]})
check(e == [], "transitive ancestor source head passes", e)

# malformed rows
e = guard_errors(fan_graph(ITEMS[:1], ["noseparator"]))
check(len(e) == 1 and "malformed source" in e[0]["msg"], "row without a dot refused", e)
e = guard_errors(fan_graph(ITEMS[:1], [42]))
check(len(e) == 1 and "must be a" in e[0]["msg"], "non-string/non-object row refused", e)

# no ledger at all -> byte-unchanged pass (no ledger, no guard)
plain = {"name": "g85p", "nodes": [agent("seed"),
                                    agent("fan", after=["seed"],
                                          fanout={"items": ITEMS, "goal": "process {item}"})]}
check(wfcommon.validate_graph_errors(plain["nodes"]) == []
      and wfcommon.admission_ledger_errors(plain) == [],
      "graph WITHOUT a ledger stays fully clean (golden-solo law)")

# items_from: count unknown at admit -> structural row laws defer, source laws run
e = guard_errors({"name": "g85d", "nodes": [
    agent("seed"),
    agent("fan", after=["seed"], fanout={"items_from": "seed.items", "goal": "x {item}",
                                         "ledger": ["seed.facts.0", "seed.facts.0"]}),
]})
check(len(e) == 1 and "already declared" in e[0]["msg"],
      "items_from graph: duplicate sources still refused", e)

# ---------------- (4) artifact bytes measured when a run dir exists ----------------
rd = HOME / "run-85"
(rd / "inputs").mkdir(parents=True)
(rd / "inputs" / "k0.bin").write_bytes(b"payload-0")
good_sha = SHA(b"payload-0")

def art_graph(art):
    return fan_graph(ITEMS[:1], [{"source": "seed.facts.0", "artifact": art}])

# structural-only pass without a run dir (run creation has none yet)
check(wfcommon.admission_ledger_errors(
          art_graph({"file": "inputs/nope.bin", "sha256": "0" * 64})) == [],
      "bytes unmeasurable without run_dir -> structural pass")

e = guard_errors(art_graph({"file": "inputs/k0.bin", "sha256": good_sha}), run_dir=rd)
check(e == [], "artifact with correct file + sha256 passes with run_dir", e)

e = guard_errors(art_graph({"file": "inputs/absent.bin"}), run_dir=rd)
check(len(e) == 1 and "missing source artifact" in e[0]["msg"],
      "absent artifact file refused naming the item", e)

e = guard_errors(art_graph({"file": "inputs/k0.bin", "sha256": "d" * 64}), run_dir=rd)
check(len(e) == 1 and "sha256 mismatch" in e[0]["msg"], "sha256 mismatch refused", e)

for bad_sha in ("abc", "z" * 64, 12, "A" * 63 + "g"):
    e = guard_errors(art_graph({"file": "inputs/k0.bin", "sha256": bad_sha}), run_dir=rd)
    check(any("sha256" in x["msg"] for x in e), f"non-hex sha256 {bad_sha!r} refused", e)

e = guard_errors(art_graph({"file": str(rd / "inputs" / "k0.bin")}), run_dir=rd)
check(len(e) == 1 and "relative path" in e[0]["msg"], "absolute artifact.file refused", e)
e = guard_errors(art_graph({"file": "../outside.bin"}), run_dir=rd)
check(len(e) == 1 and "escapes the run dir" in e[0]["msg"], "path-escape artifact.file refused", e)
e = guard_errors(art_graph({"file": "inputs/k0.bin", "sig": "x"}), run_dir=rd)
check(len(e) == 1 and "unknown key" in e[0]["msg"], "artifact unknown key refused", e)
e = guard_errors(art_graph("not-an-object"), run_dir=rd)
check(len(e) == 1 and "artifact must be an object" in e[0]["msg"], "non-object artifact refused", e)

# door: validate with run_id measures bytes against a REAL run dir; unknown run_id refused
seeded = call(action="run", graph=copy.deepcopy(clean))
sid = seeded.get("run_id")
check(bool(sid), "clean ledger graph runs at the door (admission accepts 1:1)", json.dumps(seeded)[:300])
if sid:
    call(action="wait", run_id=sid, timeout=60)
_rid = Path(door.run_dir(sid)) if sid else None
if _rid and (_rid / "graph.json").exists():
    (rdir0 := _rid / "inputs").mkdir(exist_ok=True)
    (rdir0 / "k0.bin").write_bytes(b"payload-0")
    r = call(action="validate", graph=art_graph({"file": "inputs/k0.bin", "sha256": good_sha}),
             run_id=sid)
    check(r.get("ok") is True, "door validate(run_id=...) accepts a byte-true artifact", json.dumps(r)[:300])
    r = call(action="validate", graph=art_graph({"file": "inputs/k0.bin", "sha256": "e" * 64}),
             run_id=sid)
    check(r.get("ok") is False
          and any("sha256 mismatch" in x["msg"] for x in r.get("errors", [])),
          "door validate(run_id=...) refuses a byte-mismatched artifact", json.dumps(r)[:300])
else:
    check(False, "door run committed graph.json (validate probes need a real run dir)",
          json.dumps(seeded)[:200])
r = call(action="validate", graph=art_graph({"file": "inputs/k0.bin", "sha256": good_sha}),
         run_id="no-such-run")
check("unknown run_id" in json.dumps(r), "door validate refuses an unknown run_id", json.dumps(r)[:200])

# door: run refuses a missing ledger row before writing anything
before = sorted(p.name for p in (HOME / "workflows").glob("*")) if (HOME / "workflows").exists() else []
r = call(action="run", graph=copy.deepcopy(red))
after = sorted(p.name for p in (HOME / "workflows").glob("*")) if (HOME / "workflows").exists() else []
check("run_id" not in r and before == after, "refusal wrote no run dir", (before, after))

# ---------------- (5) include rewrite: ledger rows namespacing (6th surface) ----------------
LEDGERED = {"name": "aud", "nodes": [
    agent("kick"),
    agent("fan", after=["kick"], fanout={
        "items": [{"key": "a"}, {"key": "b"}], "goal": "audit {item}",
        "ledger": ["kick.facts.0",
                   {"source": "kick.facts.1", "artifact": {"file": "in/a.bin"}}]}),
]}
def reader(name):
    return copy.deepcopy(LEDGERED) if name == "aud" else None
exp, notes = wfcommon.expand_includes(
    {"name": "m", "include": [{"as": "aud", "use": "aud"}], "nodes": [agent("prep")]}, reader)
fann = next(n for n in exp["nodes"] if n["id"] == "aud__fan")
check(fann["fanout"]["ledger"][0] == "aud__kick.facts.0",
      "string ledger row source head namespaced", fann["fanout"]["ledger"])
check(fann["fanout"]["ledger"][1]["source"] == "aud__kick.facts.1"
      and fann["fanout"]["ledger"][1]["artifact"] == {"file": "in/a.bin"},
      "{source, artifact} row: source namespaced, artifact untouched", fann["fanout"]["ledger"])
check(wfcommon.admission_ledger_errors(exp) == [],
      "expanded composite passes the guard (rewritten heads resolve in-namespace)",
      wfcommon.admission_ledger_errors(exp))

shutil.rmtree(HOME, ignore_errors=True)
print(f"\n{'ALL PASS' if not fails else 'FAILURES'} ({fails} failures)")
sys.exit(1 if fails else 0)
