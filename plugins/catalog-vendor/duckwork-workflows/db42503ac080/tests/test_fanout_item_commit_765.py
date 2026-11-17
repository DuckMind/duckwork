#!/usr/bin/env python3
"""est-2ek.1.765 — a fan-out aggregate may never be done while canonical
per-item records remain uncommitted (`running` with no output).

Defect (evidence run 20261006-191154-zap-priority-peer-queue): `nodes/
other_readers.json` and `nodes/other_witnesses.json` committed status=done with
"COMPLETE" all_results while ALL twelve canonical per-item records
`nodes/other_readers.N.json` / `nodes/other_witnesses.N.json` still carried the
spawn-time record — status=running, no output — despite every item having
finished. The per-item file was written exactly once (write_spawn_record, before
Popen) and never finalized by the normal happy path, so the aggregate's
done/all_results was never DERIVED from committed per-item truth — and a
downstream reducer that (correctly) refuses to certify on `individual record
says running` held PR eligibility unknown while two witnesses had actually
finished.

The fix this pins (single-writer ordering):
  1. every item result is committed to `nodes/<node>.<i>.json` by ONE writer
     (`commit_item_record`, the item's own worker thread) BEFORE the
     `item.finished` event, and before the aggregate commit;
  2. the aggregate's done is validated against the committed per-item records
     re-read from disk (`item_records_certified`): a missing / uncommitted /
     efp-invalid / output-diverging record demotes the aggregate to failed
     (error_class=item_record) — never done with claimed-complete results;
  3. nothing fabricates an individual completion: the record only ever carries
     the runner's real harvest result.

Invariant asserted after EVERY run below:
  aggregate `done`  =>  every per-item record is a committed fact (status
  done|partial|failed|skipped, efp-valid against the graph) whose committed
  output backs the aggregate's all_results for done/partial rows.

RED-proof (run against the pre-fix engine, HEAD~ of this PR):
  test_aggregate_done_implies_committed_item_records FAILS — 3/3 item records
  read status=running with no output under a done aggregate (the evidence-run
  shape, reproduced with zero injection); the crash test's done-branch
  assertion FAILS on the same shape; the ordering test FAILS with
  "no item.finalized commit observed before any item.finished" (the pre-fix
  engine never calls commit_item_record). Runnable two ways (repo
  convention): `PYTHONPATH=/opt/duckwork python3 tests/test_fanout_item_commit_765.py`
  prints PASS/FAIL lines, exit 0 = green; pytest can also collect the test_*
  functions directly.
"""
import json, os, subprocess, sys, tempfile, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wf            # noqa: E402
import wfcommon      # noqa: E402

FAKE = str(HERE / "fake")
N = 3
SCHEMA = {"type": "object", "required": ["result"],
          "properties": {"result": {"type": "string"}}}

fails = total = 0
def check(name, ok, detail=""):
    global fails, total
    total += 1
    print(("PASS " if ok else "FAIL " + name) + (f" :: {detail[:300]}" if detail and not ok else ""), flush=True)
    if not ok:
        fails += 1

# ---- isolated harness (empty DUCKWORK_HOME + mktemp WF_RUNS_ROOT; hostile WF_*
# and FAKE_* stripped so an inherited env can never steer the engine) ----
_scratch = Path(tempfile.mkdtemp(prefix="wf765-"))
BASE_ENV = {k: v for k, v in os.environ.items()
            if not k.startswith("WF_") and not k.startswith("FAKE_")
            and not k.startswith("DUCKWORK_WF_")
            and k not in ("DUCKWORK_HOME",)}
BASE_ENV["DUCKWORK_HOME"] = str(_scratch / "home")
BASE_ENV["WF_RUNS_ROOT"] = str(_scratch / "runs")
BASE_ENV["FAKE_LOG"] = str(_scratch / "fake.log")
os.makedirs(BASE_ENV["DUCKWORK_HOME"], exist_ok=True)

import shutil

def mk(run_id, graph, item_concurrency=3):
    r = Path(BASE_ENV["WF_RUNS_ROOT"]) / run_id
    if r.exists():
        shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(graph))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE,
                                            "item_concurrency": item_concurrency}))
    return r

def fan_graph(items, quorum=None, timeout=30):
    fo = {"items": items, "goal": "PROCESS item {index} reply", "schema": SCHEMA}
    if quorum is not None:
        fo["quorum"] = quorum
    return {"name": "est-765-fanout", "nodes": [
        {"id": "fan", "type": "agent", "fanout": fo, "timeout": timeout}]}

def wf_cmd(run_id, extra_env=None, timeout=120):
    env = dict(BASE_ENV)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout)

def item_records(r):
    out = {}
    for p in sorted((r / "nodes").glob("fan.[0-9]*.json")):
        i = int(p.stem.split(".")[1])
        try:
            out[i] = json.loads(p.read_text())
        except Exception:
            out[i] = None
    return out

def agg_record(r):
    try:
        return json.loads((r / "nodes" / "fan.json").read_text())
    except Exception:
        return None

CURRENT_GRAPH = {"graph": None}

def check_invariant(label, r):
    """THE law: aggregate done => every canonical per-item record is an efp-valid
    committed fact whose output backs the aggregate's all_results. Every legal
    non-done state passes vacuously (nothing claims completion)."""
    agg = agg_record(r)
    recs = item_records(r)
    graph = CURRENT_GRAPH["graph"]
    node = graph["nodes"][0]
    byid = {n["id"]: n for n in graph["nodes"]}
    if agg is None or agg.get("status") != "done":
        if agg is not None and agg.get("status") == "failed" \
                and agg.get("error_class") == "item_record":
            check(f"{label}: aggregate honestly refused done over unbackable items", True)
        else:
            check(f"{label}: non-done aggregate needs no per-item certification (vacuous)", True)
        return
    if not recs:
        check(f"{label}: done aggregate with ZERO per-item records", False,
              "aggregate claims completion but no canonical individual record exists")
        return
    all_results = (agg.get("output") or {}).get("all_results") or []
    problems = []
    for i in range(len(all_results)):
        rec = recs.get(i)
        if rec is None:
            problems.append(f"[{i}] record file missing")
            continue
        st = rec.get("status")
        if st == "running":
            problems.append(f"[{i}] status=running no_output={rec.get('output') is None} "
                            "(spawn-time record never finalized — the evidence-run shape)")
            continue
        if st not in ("done", "partial", "failed", "skipped"):
            problems.append(f"[{i}] status={st!r} is not a committed fact")
            continue
        if not wfcommon.record_efp_valid(rec, byid, node):
            problems.append(f"[{i}] committed record is not efp-valid")
            continue
        want = all_results[i] if i < len(all_results) else None
        if want is not None and want.get("status") in ("done", "partial"):
            if rec.get("output") is None:
                problems.append(f"[{i}] aggregate says done item but record has no committed output")
            elif json.dumps(rec.get("output"), sort_keys=True, default=str) != \
                    json.dumps(want.get("output"), sort_keys=True, default=str):
                problems.append(f"[{i}] record output diverges from aggregate all_results")
    check(f"{label}: aggregate done => all {len(all_results)} per-item records are efp-valid "
          f"committed facts consistent with all_results", not problems, "; ".join(problems))

# ---------------------------------------------------------------- tests ----

def test_aggregate_done_implies_committed_item_records():
    """Honest 3-item fan-out, no injection: aggregate done must be backed by
    committed per-item records. RED on the pre-fix engine: all three records
    sit at the spawn-time status=running with no output — the exact evidence
    shape (aggregate done + COMPLETE all_results, individuals uncommitted)."""
    graph = fan_graph([{"n": i} for i in range(N)])
    CURRENT_GRAPH["graph"] = graph
    r = mk("est765-honest", graph)
    out = wf_cmd("est765-honest").stdout
    assert "WORKFLOW_DONE" in out, out
    check_invariant("est765-honest", r)
    recs = item_records(r)
    check("est765-honest: every item record committed with real output",
          len(recs) == N and all(x and x.get("status") in ("done", "partial")
                                 and x.get("output") is not None for x in recs.values()),
          str({k: (v or {}).get("status") for k, v in recs.items()}))
    # spawn evidence survived the finalize (merge, not clobber)
    check("est765-honest: finalized records retain spawn evidence",
          all(x.get("spawn_cmd") and x.get("log_path") and x.get("skey")
              for x in recs.values() if x))
    st = wfcommon.run_state(r)
    check("est765-honest: read model still done", st["status"] == "done", str(st["status"]))

def test_crash_between_harvest_and_commit_never_leaves_done_with_running_item():
    """Deterministic kill at item 1's finalize instant (runner SIGKILLs itself
    inside commit_item_record, before the atomic swap — child answer harvested,
    canonical record NOT yet committed). Respawn (plain CLI boot) without the
    hook: item 1's dead running record fails active_child verification -> fresh
    re-drive -> committed. Final state must obey the invariant, and item 1 must
    end as a committed fact."""
    graph = fan_graph([{"n": i} for i in range(N)])
    CURRENT_GRAPH["graph"] = graph
    r = mk("est765-crash", graph)
    p1 = wf_cmd("est765-crash", extra_env={"WF_TEST_KILL_ITEM_AT_FINALIZE": "1"})
    check("est765-crash: runner died at the finalize hook (no verdict emitted)",
          "WORKFLOW_" not in p1.stdout, p1.stdout[-160:])
    rec1 = item_records(r).get(1) or {}
    check("est765-crash setup: item 1 was caught mid-finalize (record still spawn-time)",
          rec1.get("status") == "running", f"item1 status={rec1.get('status')}")
    out = wf_cmd("est765-crash").stdout          # crash-respawn, hook removed
    check("est765-crash: resumed run finishes", "WORKFLOW_DONE" in out, out[-200:])
    check_invariant("est765-crash", r)
    rec1 = item_records(r).get(1) or {}
    agg = agg_record(r) or {}
    check("est765-crash: item 1 re-driven to a committed done fact",
          agg.get("status") == "done" and rec1.get("status") in ("done", "partial")
          and rec1.get("output") is not None,
          f"item1 status={rec1.get('status')} has_output={rec1.get('output') is not None} "
          f"agg={agg.get('status')}")

def test_single_writer_ordering_commit_precedes_item_finished():
    """In-process: wrap wf.commit_item_record and wf.log to capture the real
    call order inside one() — for EVERY item the canonical commit must be
    observed BEFORE that item's item.finished event, and all commits before the
    aggregate save_node. (The engine's happy-path event vocabulary is frozen by
    golden-solo, so the ordering fact is captured by wrapping, not by a new
    event type.)"""
    graph = fan_graph([{"n": i} for i in range(N)])
    CURRENT_GRAPH["graph"] = graph
    r = mk("est765-order", graph)
    trace = []
    trace_lock = threading.Lock()
    real_commit = wf.commit_item_record
    real_log = wf.log
    real_save = wf.save_node
    def spy_commit(run, node, byid, index, result):
        with trace_lock:
            trace.append(("commit", index, result.get("status")))
        return real_commit(run, node, byid, index, result)
    def spy_log(run, ev, **kw):
        if ev == "item.finished":
            with trace_lock:
                trace.append(("finished", kw.get("index"), kw.get("status")))
        return real_log(run, ev, **kw)
    def spy_save(run, node, byid, rec):
        if node["id"] == "fan" and "." not in node["id"]:
            with trace_lock:
                trace.append(("aggregate", None, rec.get("status")))
        return real_save(run, node, byid, rec)
    wf.commit_item_record = spy_commit
    wf.log = spy_log
    wf.save_node = spy_save
    try:
        # drive run_agent_node directly: minimal meta, same shape main() builds
        meta = dict(jload_runjson(r))
        meta.update({"_run": r, "_procs": {}, "_procs_lock": threading.Lock(),
                     "_stop": threading.Event(), "_spawn_n": {}, "_retries_left": 6,
                     "_subreaper": False})
        byid = {n["id"]: n for n in graph["nodes"]}
        wf.run_agent_node(r, meta, byid, graph["nodes"][0], {}, {})
    finally:
        wf.commit_item_record = real_commit
        wf.log = real_log
        wf.save_node = real_save
    commits = {}
    finishes = {}
    agg_pos = None
    for pos, (kind, idx, _st) in enumerate(trace):
        if kind == "commit":
            commits.setdefault(idx, pos)
        elif kind == "finished":
            finishes.setdefault(idx, pos)
        elif kind == "aggregate":
            agg_pos = pos
    bad = []
    for i in finishes:
        if i not in commits:
            bad.append(f"item {i}: item.finished with NO preceding commit call")
        elif commits[i] > finishes[i]:
            bad.append(f"item {i}: commit AFTER item.finished")
    check("est765-order: every item.finished is preceded by its per-item commit",
          not bad and len(commits) == N, "; ".join(bad) or f"commits={sorted(commits)}")
    check("est765-order: the aggregate save happens after ALL per-item commits",
          agg_pos is not None and all(c < agg_pos for c in commits.values()),
          f"agg@{agg_pos} commits={sorted(commits.values())}")

def jload_runjson(r):
    try:
        return json.loads((r / "run.json").read_text())
    except Exception:
        return {}

def test_forged_complete_aggregate_cannot_commit_done():
    """Fabrication guard (gate path, direct): an aggregate whose in-memory
    results claim a done item while the canonical record on disk does not back
    it must be REFUSED by item_records_certified — done with claimed-complete
    results over an unbackable item is structurally impossible."""
    graph = fan_graph([{"n": i} for i in range(2)])
    CURRENT_GRAPH["graph"] = graph
    r = mk("est765-forged", graph)
    byid = {n["id"]: n for n in graph["nodes"]}
    node = graph["nodes"][0]
    # item 0: no record at all; item 1: a done record with DIFFERENT output
    (r / "nodes" / "fan.1.json").write_text(json.dumps(
        {"status": "done", "output": {"result": "NOT WHAT THE AGGREGATE CLAIMS"},
         "efp": wf.efp(byid, node), "fp_rule_version": wf.FP_RULE_VERSION}))
    fake_results = [{"status": "done", "output": {"result": "ok"}},
                    {"status": "done", "output": {"result": "ok"}}]
    ok, problems = wf.item_records_certified(r, node, byid, fake_results)
    check("est765-forged: aggregate over unbackable items is refused",
          ok is False and len(problems) == 2, f"ok={ok} problems={problems}")
    # and the honest path certifies
    for i, res in enumerate(fake_results):
        wf.commit_item_record(r, node, byid, i, res)
    ok2, problems2 = wf.item_records_certified(r, node, byid, fake_results)
    check("est765-forged: honest commits certify clean", ok2 is True, str(problems2))

def _status_mismatch_control(run_id, error_class):
    """Real-seam control (zap r4, PR #258): the canonical record is committed
    failed+<error_class> via the shipped producer, while the aggregate row
    claims done with the SAME output bytes. item_records_certified must refuse:
    a committed failure never certifies a done claim, matched outputs or not."""
    graph = fan_graph([{"n": i} for i in range(2)])
    CURRENT_GRAPH["graph"] = graph
    r = mk(run_id, graph)
    byid = {n["id"]: n for n in graph["nodes"]}
    node = graph["nodes"][0]
    out = {"result": "ok"}
    wf.commit_item_record(r, node, byid, 0, {"status": "done", "output": out})
    wf.commit_item_record(r, node, byid, 1, {"status": "failed", "output": out,
                                             "error": f"child {error_class}",
                                             "error_class": error_class})
    rec1 = json.loads((r / "nodes" / "fan.1.json").read_text())
    check(f"{run_id}: setup — committed failed/{error_class} record carries the "
          "matching output",
          rec1.get("status") == "failed" and rec1.get("error_class") == error_class
          and rec1.get("output") == out, json.dumps(rec1)[:200])
    results = [{"status": "done", "output": out}, {"status": "done", "output": out}]
    ok, problems = wf.item_records_certified(r, node, byid, results)
    check(f"{run_id}: aggregate done is REFUSED over a failed/{error_class} record "
          "whose output matches the claim",
          ok is False and any(p.get("index") == 1 for p in problems),
          f"ok={ok} problems={problems}")

def test_failed_crashed_record_cannot_certify_done_row():
    """(a) failed+crashed per-item record must block a done aggregate row."""
    _status_mismatch_control("est765-st-crashed", "crashed")

def test_failed_cancelled_record_cannot_certify_done_row():
    """(b) failed+cancelled per-item record must block a done aggregate row."""
    _status_mismatch_control("est765-st-cancelled", "cancelled")

def test_quorum_straggler_cancel_keeps_invariant():
    """quorum=2 of 3 with a QSLEEP straggler cancelled at quorum: the aggregate
    commits done on the two survivors; the cancelled item's record must still be
    a committed fact (failed+cancelled — never a frozen running record)."""
    items = [{"goal": f"PROCESS item {i} reply"} for i in range(2)]
    items.append({"goal": "PROCESS item 2 reply QSLEEP 25"})
    graph = fan_graph(items, quorum=2, timeout=40)
    CURRENT_GRAPH["graph"] = graph
    r = mk("est765-quorum", graph)
    out = wf_cmd("est765-quorum").stdout
    assert "WORKFLOW_DONE" in out, out
    agg = agg_record(r)
    check("est765-quorum: aggregate done on survivors", agg.get("status") == "done",
          str(agg.get("status")))
    check_invariant("est765-quorum", r)
    rec2 = item_records(r).get(2) or {}
    check("est765-quorum: cancelled straggler has a committed record (not running)",
          rec2.get("status") in ("done", "partial", "failed", "skipped"),
          f"item2 status={rec2.get('status')}")

def main():
    for fn in (test_aggregate_done_implies_committed_item_records,
               test_crash_between_harvest_and_commit_never_leaves_done_with_running_item,
               test_single_writer_ordering_commit_precedes_item_finished,
               test_forged_complete_aggregate_cannot_commit_done,
               test_failed_crashed_record_cannot_certify_done_row,
               test_failed_cancelled_record_cannot_certify_done_row,
               test_quorum_straggler_cancel_keeps_invariant):
        try:
            fn()
        except Exception as e:
            import traceback; traceback.print_exc()
            check(fn.__name__ + " (raised)", False, f"{type(e).__name__}: {e}")
    print(f"TOTAL {total - fails} PASS {fails} FAIL", flush=True)
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
