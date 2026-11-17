"""The partial-rescue law (issue #134): the committed nodes/*.json done-set
parsed against the CURRENT graph is the only saved recovery state — editing the
submitted graph changes what a rerun does (amend-via-efp is the sanctioned
recovery path), so the plugin carries no rescue-snapshot file by design: one
less thing to keep in sync.

Pure read-model test: no runner spawn, no door call. Node records are written
directly with the efp stamps the runner would write, exactly like
test_amend_preview_defdiff does. Checks pin: the done-set reads done against
disk truth; an amended ancestor def demotes its own AND its untouched
descendant's committed records to pending; amend_preview agrees with node_rec
on the same bytes (preview and runner share one law).
"""
import json, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN))
import wfcommon  # noqa: E402

RUNS = HERE / "home-partialrescue134" / "workflows"
FAILS = []

def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)

def agent(id, after=(), **kw):
    n = {"id": id, "type": "agent", "after": list(after), "timeout": 30, "goal": "say hi"}
    n.update(kw)
    return n

def fresh(run_id, nodes):
    r = RUNS / run_id
    if r.exists():
        shutil.rmtree(r)
    for d in ("nodes", "gates", "logs"):
        (r / d).mkdir(parents=True)
    (r / "graph.json").write_text(json.dumps({"name": "t", "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"name": "t", "duckwork_bin": "fake", "concurrency": 4,
                                            "started": "2026-10-06T00:00:00+00:00", "owner": "test"}))
    return r

# a -> b: both committed done, efp computed against the graph as written.
base = [agent("a", model="m-a", provider="p1"),
        agent("b", ["a"], model="m-b", provider="p2")]
r = fresh("20991006-000000-partialrescue134", base)
byid = {n["id"]: n for n in base}
for n in base:
    (r / "nodes" / f"{n['id']}.json").write_text(json.dumps(
        {"status": "done", "efp": wfcommon.efp(byid, n), "output": {"ok": True}}))

# 1. done-set truth: both committed records read done against the on-disk graph.
st_a, _ = wfcommon.node_rec(r, byid["a"], byid)
st_b, _ = wfcommon.node_rec(r, byid["b"], byid)
check("committed done-set reads done against the current graph",
      st_a == "done" and st_b == "done", f"{st_a}/{st_b}")

# 2. amend the graph the way act_amend does (replace graph.json over the old
#    bytes), editing ONLY ancestor a's def. b's own def is byte-identical — its
#    record must still go pending because efp sees the changed ancestor through
#    the CURRENT graph. If any code ever trusted a stored graph copy, b would
#    stay done.
amended = [dict(base[0], goal="say hi differently"), dict(base[1])]
(r / "graph.json").write_text(json.dumps({"name": "t", "nodes": amended}))
byid_new = {n["id"]: n for n in amended}
st_a2, _ = wfcommon.node_rec(r, byid_new["a"], byid_new)
st_b2, _ = wfcommon.node_rec(r, byid_new["b"], byid_new)
check("amended ancestor def demotes its own record to pending",
      st_a2 == "pending", st_a2)
check("amended ancestor def demotes the UNTOUCHED descendant record to pending",
      st_b2 == "pending", st_b2)

# 3. the door's preview applies the same law on the same bytes: a,b were both
#    committed and are now efp-stale, so BOTH land in `changed` (committed but
#    efp-stale is the committed_mismatch arm of the preview law) and the
#    preview's will_rerun matches the node_rec verdicts exactly.
pv = wfcommon.amend_preview(r, amended)
check("amend_preview agrees with node_rec: will_rerun=[a,b], neither stays unchanged",
      pv["will_rerun"] == ["a", "b"] and pv["unchanged"] == [], json.dumps(pv))

print(f"\n{'ALL PASS' if not FAILS else 'FAILED: ' + ', '.join(FAILS)} ({4 - len(FAILS)}/4)")
sys.exit(1 if FAILS else 0)
