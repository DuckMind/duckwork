#!/usr/bin/env python3
"""#733 dead-on-arrival finalize — scripts/lane_recover.py --finalize <run-dir>.

The incident shape (census 2026-10-06, 63 stale records on the estate + profile
shelves): a runner is SIGKILLed out-of-band; the door's silent-death reaper makes
the death LOUD (events) but, by its own law, leaves the falsely-claimed records
byte-intact ("a reaper must not erase the crime scene"), and the lane-reaper cron
respawns. Some lanes never get a replacement runner: nodes/*.json claim
status="running" with a dead child forever and the run reads non-terminal —
neither the census nor the dashboard can tell a dead-on-arrival claim from live
work.

Law pinned here (the finalize step, an EXPLICIT act the reaper-caller invokes —
never a passive read, never the door's respawn reaper, whose bytes are pinned by
tests/test_silent_death_reaper_8 to stay event-only):
  * dead runner (own pid dead + runner.lock held by nobody) => every node record
    claiming status="running" whose spawn record fails the ONE verification law
    (_verify_spawn_rec: a verifiably-live child is NEVER finalized) is finalized:
    status="failed", finalized="dead-on-arrival", death_cause + finished_at, efp
    stamped from the spawn record so node_rec reads it as a terminal commit;
  * committed statuses (done/partial/skipped) and never-spawned (absent) records
    are untouched;
  * the run gets a terminal runner_exit.json (reason "blocked by dead-on-arrival
    ...") ONLY if no authoritative verdict already stands;
  * a verifiable exit record (reason + matching graph_fingerprint) is NEVER
    overwritten;
  * idempotent: a second finalize changes no bytes;
  * alive runner (live pid OR held runner.lock — the cross-container law) =>
    zero writes, exit 3;
  * no wf.pid = fresh/never-spawned run => zero writes, exit 2;
  * finalize never mutates the run BEFORE deciding (no litter).
  * fan-out: per-item records finalize independently; the parent base record
    with no claim is left alone.

Plain script, no pytest: exits non-zero on the first red (the lane_recover /
silent_death harness idiom).
"""
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "scripts" / "lane_recover.py"

checks = 0
failures = 0


def check(label, cond, detail=""):
    global checks, failures
    checks += 1
    if cond:
        print(f"PASS {label}")
    else:
        failures += 1
        print(f"FAIL {label}: {detail}")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lr = load("lane_recover_733", SCRIPT)
wc = lr._wfcommon()
if wc is None:
    print("SKIP test_stuck_node_finalize_733: wfcommon not importable beside the script")
    sys.exit(0)


def dead_pid():
    """A pid we spawned, reaped, and know is gone (non-zero exit -> os.kill 3)."""
    p = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(7)"])
    p.wait()
    return p.pid


def mk_run(runs, run_id, graph, nodes):
    """Synthetic run dir: graph.json + nodes/*.json (efp-stamped via wfcommon.efp,
    the spawn-record vocabulary) + optional extra files. Returns the run path."""
    r = runs / run_id
    r.mkdir(parents=True, exist_ok=True)
    (r / "nodes").mkdir(exist_ok=True)
    (r / "gates").mkdir(exist_ok=True)
    (r / "graph.json").write_text(json.dumps(graph))
    byid = {n["id"]: n for n in graph["nodes"]}
    for name, rec in nodes.items():
        nid, _, idx = name.partition(":")
        n = byid[nid]
        rec = dict(rec)
        if rec.get("status") == "running":
            rec.setdefault("efp", wc.efp(byid, n))
            rec.setdefault("fp_rule_version", wc.FP_RULE_VERSION)
        (r / "nodes" / f"{name.replace(':', '.')}.json").write_text(json.dumps(rec))
    return r


GRAPH = {"name": "synthetic-stuck", "nodes": [
    {"id": "build", "type": "agent", "goal": "build it"},
    {"id": "adversary", "type": "agent", "goal": "judge it", "after": ["build"]},
]}


def base_nodes(dp):
    return {
        "build": {"status": "running", "pid": dp, "skey": "wf:syn:build:abcd.0001",
                  "attempt": 0, "started": "2026-10-06T00:00:00+00:00",
                  "log_path": "logs/build.log"},
        "adversary": {"status": "running", "pid": dp + 1, "skey": "wf:syn:adversary:abcd.0002",
                      "attempt": 0, "started": "2026-10-06T00:00:00+00:00",
                      "log_path": "logs/adversary.log"},
    }


def seed_exit_reason(r, reason, valid=True, graph=None):
    rec = {"reason": reason, "at": "2026-10-06T01:00:00+00:00"}
    if valid:
        g = graph if graph is not None else json.loads((r / "graph.json").read_text())
        rec["graph_fingerprint"] = wc.graph_fingerprint(g)
        rec["fp_rule_version"] = wc.FP_RULE_VERSION
    (r / "runner_exit.json").write_text(json.dumps(rec))


with tempfile.TemporaryDirectory() as td:
    runs = Path(td) / "runs"
    runs.mkdir()

    # ---- 1. dead runner + two falsely-claimed nodes -> both finalized, run blocked
    dp = dead_pid()
    r = mk_run(runs, "dead-1", GRAPH, base_nodes(dp))
    (r / "wf.pid").write_text(str(dp) + "\n")
    before = {p.name: p.read_bytes() for p in (r / "nodes").glob("*.json")}
    rc = lr.finalize_run(r)
    check("exit 0 when it finalized", rc == 0, f"rc={rc}")
    for name in ("build.json", "adversary.json"):
        rec = json.loads((r / "nodes" / name).read_text())
        check(f"{name} -> failed", rec.get("status") == "failed", rec)
        check(f"{name} finalized marker", rec.get("finalized") == "dead-on-arrival", rec)
        check(f"{name} has death_cause", bool(rec.get("death_cause")), rec)
        check(f"{name} has finished_at", bool(rec.get("finished_at")), rec)
    rx = json.loads((r / "runner_exit.json").read_text())
    # zap F1 (#235 review): the verdict must be one the read model already
    # classifies — the runner's own "blocked by failed <ids>" vocabulary; the
    # dead-on-arrival provenance rides in detail + the finalized marker.
    check("run terminal 'blocked by failed' verdict (read-model vocabulary)",
          str(rx.get("reason", "")).startswith("blocked by failed "), rx)
    check("verdict detail names dead-on-arrival", "dead-on-arrival" in str(rx.get("detail", "")), rx)
    check("run_state reads the finalized run as failed",
          (wc.run_state(r) or {}).get("status") == "failed", (wc.run_state(r) or {}).get("status"))
    evs = [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]
    check("run.finalized_doa event written",
          any(e.get("event") == "run.finalized_doa" for e in evs), evs)
    check("spawned-from record kept its evidence (skey/pid)",
          json.loads((r / "nodes" / "build.json").read_text()).get("skey") == "wf:syn:build:abcd.0001")

    # ---- 2. idempotent: a second finalize changes no bytes
    snap = {p.name: p.read_bytes() for p in (r / "nodes").glob("*.json")}
    snap["runner_exit.json"] = (r / "runner_exit.json").read_bytes()
    ev_count = len((r / "events.jsonl").read_text().splitlines())
    rc2 = lr.finalize_run(r)
    check("second finalize exits 0 (nothing to do)", rc2 == 0, f"rc={rc2}")
    after = {p.name: p.read_bytes() for p in (r / "nodes").glob("*.json")}
    after["runner_exit.json"] = (r / "runner_exit.json").read_bytes()
    check("idempotent: no record bytes changed", snap == after)
    check("idempotent: no extra events", len((r / "events.jsonl").read_text().splitlines()) == ev_count)

    # ---- 3. committed statuses and never-spawned records are untouched
    r3 = mk_run(runs, "mixed-3", GRAPH, {
        "build": {"status": "done", "output": {"result": "shipped"},
                  "efp": wc.efp({n["id"]: n for n in GRAPH["nodes"]}, GRAPH["nodes"][0]),
                  "fp_rule_version": wc.FP_RULE_VERSION},
        "adversary": {"status": "running", "pid": dp, "skey": "wf:syn:adversary:abcd.0009",
                      "attempt": 0},
    })
    (r3 / "wf.pid").write_text(str(dp) + "\n")
    lr.finalize_run(r3)
    rec_b = json.loads((r3 / "nodes" / "build.json").read_text())
    check("done commit untouched", rec_b.get("status") == "done" and "finalized" not in rec_b, rec_b)
    rec_a = json.loads((r3 / "nodes" / "adversary.json").read_text())
    check("running claim finalized", rec_a.get("status") == "failed"
          and rec_a.get("finalized") == "dead-on-arrival", rec_a)
    st3, _ = wc.node_rec(r3, GRAPH["nodes"][1], {n["id"]: n for n in GRAPH["nodes"]})
    check("node_rec reads the finalize as a terminal commit", st3 == "failed", st3)

    # r3 with an absent record: never-spawned stays absent
    r4 = mk_run(runs, "mixed-4", GRAPH, {
        "build": {"status": "running", "pid": dp, "skey": "wf:syn:build:abcd.0010",
                  "attempt": 0},
    })
    (r4 / "wf.pid").write_text(str(dp) + "\n")
    (r4 / "nodes" / "adversary.json").unlink(missing_ok=True)
    lr.finalize_run(r4)
    check("absent record stays absent", not (r4 / "nodes" / "adversary.json").exists())
    # (the build claim WAS finalized, so this run is blocked — but the absent
    # node was never fabricated)
    rec_b4 = json.loads((r4 / "nodes" / "build.json").read_text())
    check("build claim finalized in mixed-4", rec_b4.get("finalized") == "dead-on-arrival", rec_b4)

    # ---- 4. verifiably-live child is NEVER finalized (the ONE verification law)
    sp = "wf:syn:live:abcd.0003"
    proc = subprocess.Popen([sys.executable, "-c",
                             "import time; time.sleep(120)", sp + "#a0"])
    try:
        r5 = mk_run(runs, "live-5", GRAPH, {
            "build": {"status": "running", "pid": proc.pid, "skey": sp, "attempt": 0},
            "adversary": {"status": "running", "pid": dp, "skey": "wf:syn:adversary:abcd.0004",
                          "attempt": 0},
        })
        (r5 / "wf.pid").write_text(str(dp) + "\n")  # runner dead, one child still live
        time.sleep(0.3)
        lr.finalize_run(r5)
        rec_live = json.loads((r5 / "nodes" / "build.json").read_text())
        rec_dead = json.loads((r5 / "nodes" / "adversary.json").read_text())
        check("live child adopted, not finalized", rec_live.get("status") == "running"
              and "finalized" not in rec_live, rec_live)
        check("dead sibling claim finalized", rec_dead.get("finalized") == "dead-on-arrival", rec_dead)
        rx5 = json.loads((r5 / "runner_exit.json").read_text())
        check("run blocked only listing the dead claim",
              "adversary" in rx5.get("reason", "") and "build" not in rx5.get("reason", ""), rx5)
    finally:
        proc.kill()
        proc.wait()

    # ---- 5. alive runner: held flock (cross-container law) => zero writes
    r6 = mk_run(runs, "alive-6", GRAPH, base_nodes(dp))
    (r6 / "wf.pid").write_text(str(dp) + "\n")
    (r6 / "runner.lock").write_text("")
    hold = os.open(str(r6 / "runner.lock"), os.O_RDWR)
    fcntl.flock(hold, fcntl.LOCK_EX)
    try:
        rc6 = lr.finalize_run(r6)
        check("held runner.lock => exit 3", rc6 == 3, f"rc={rc6}")
        recs6 = {p.name: json.loads(p.read_text()) for p in (r6 / "nodes").glob("*.json")}
        check("held runner: nothing finalized",
              all(r_.get("status") == "running" and "finalized" not in r_ for r_ in recs6.values()), recs6)
        check("held runner: no runner_exit written", not (r6 / "runner_exit.json").exists())
    finally:
        fcntl.flock(hold, fcntl.LOCK_UN)
        os.close(hold)

    # ---- 6. an authoritative recorded exit is NEVER overwritten
    r7 = mk_run(runs, "verdict-7", GRAPH, base_nodes(dp))
    (r7 / "wf.pid").write_text(str(dp) + "\n")
    seed_exit_reason(r7, "done")
    lr.finalize_run(r7)
    rx7 = json.loads((r7 / "runner_exit.json").read_text())
    check("valid recorded exit kept", rx7.get("reason") == "done", rx7)
    rec7 = json.loads((r7 / "nodes" / "build.json").read_text())
    check("claims still finalized under a kept verdict",
          rec7.get("finalized") == "dead-on-arrival", rec7)

    # ---- 7. an amend-staled exit record is a VERDICT, never overwritten
    # (PR #82 review, F2 law: fingerprint staleness alone is not evidence of an
    # unrecorded death; only "crashed (no exit record)" proves the scene unwritten).
    r8 = mk_run(runs, "stale-8", GRAPH, base_nodes(dp))
    (r8 / "wf.pid").write_text(str(dp) + "\n")
    seed_exit_reason(r8, "done", valid=False)
    lr.finalize_run(r8)
    rx8 = json.loads((r8 / "runner_exit.json").read_text())
    check("amend-staled exit kept, never overwritten",
          rx8.get("reason") == "done", rx8)

    # ---- 8. no wf.pid = fresh run => zero writes, exit 2
    r9 = mk_run(runs, "fresh-9", GRAPH, base_nodes(dp))
    rc9 = lr.finalize_run(r9)
    check("fresh run => exit 2", rc9 == 2, f"rc={rc9}")
    check("fresh run: nothing finalized",
          all(json.loads(p.read_text()).get("status") == "running"
              for p in (r9 / "nodes").glob("*.json")))
    check("fresh run: no runner_exit written", not (r9 / "runner_exit.json").exists())

    # ---- 9. fan-out: per-item finalize, parent base record without a claim untouched
    FO = {"name": "synthetic-fo", "nodes": [
        {"id": "lanes", "type": "agent", "goal": "audit",
         "fanout": {"items": ["a", "b"], "goal": "audit {item}"}},
    ]}
    byid = {n["id"]: n for n in FO["nodes"]}
    r10 = mk_run(runs, "fan-10", FO, {
        "lanes:0": {"status": "done", "output": {"ok": True}},
        "lanes:1": {"status": "running", "pid": dp, "skey": "wf:syn:lanes:abcd.0005",
                    "attempt": 0},
    })
    (r10 / "wf.pid").write_text(str(dp) + "\n")
    lr.finalize_run(r10)
    rec_a10 = json.loads((r10 / "nodes" / "lanes.0.json").read_text())
    rec_b10 = json.loads((r10 / "nodes" / "lanes.1.json").read_text())
    check("fan-out done item untouched", rec_a10.get("status") == "done" and "finalized" not in rec_a10, rec_a10)
    check("fan-out dead item finalized",
          rec_b10.get("status") == "failed" and rec_b10.get("finalized") == "dead-on-arrival", rec_b10)
    # zap F1 (#235 review): a finalized item must leave the PARENT terminal —
    # node_rec reads only the aggregate, so an absent aggregate read pending
    # and the run stayed `interrupted`. The finalize commits a failed aggregate
    # (current efp, items' own efp proven current) the read model reports.
    agg10 = wc.jload(r10 / "nodes" / "lanes.json") or {}
    check("fan-out parent gets a failed dead-on-arrival aggregate",
          agg10.get("status") == "failed" and agg10.get("finalized") == "dead-on-arrival", agg10)
    st10, _ = wc.node_rec(r10, FO["nodes"][0], byid)
    check("fan-out parent reads failed in node_rec (not pending)", st10 == "failed", st10)
    rs10 = wc.run_state(r10) or {}
    check("fan-out run_state reads failed (not interrupted)", rs10.get("status") == "failed",
          rs10.get("status"))
    rx10 = json.loads((r10 / "runner_exit.json").read_text())
    check("fan-out run blocked names the item", "lanes" in rx10.get("reason", ""), rx10)

    # ---- 10. dead runner whose pid is ALSO recycled-live is still dead-on-arrival:
    # the runner decision uses wfcommon.runner_alive; with no lock + dead pid the
    # finalize proceeds (the census shape). Already covered by case 1.
    # ---- 11. unknown run dir => exit 2, no exception
    try:
        rc11 = lr.finalize_run(runs / "does-not-exist")
        check("unknown run dir => exit 2", rc11 == 2, f"rc={rc11}")
    except Exception as e:
        check("unknown run dir => exit 2 (no raise)", False, f"{type(e).__name__}: {e}")

    # ---- 12. CLI: --finalize through main() honors --home and reports counts
    r12 = mk_run(runs, "cli-12", GRAPH, base_nodes(dp))
    (r12 / "wf.pid").write_text(str(dp) + "\n")
    code = lr.main(["--finalize", str(r12)])
    check("main --finalize => exit 0", code == 0, f"rc={code}")
    check("cli finalized both claims",
          all(json.loads((r12 / "nodes" / f).read_text()).get("finalized") == "dead-on-arrival"
              for f in ("build.json", "adversary.json")))

# ======== #235 zap review (verdict=changes @21316e6dd): one behavioral scene per finding ========
import wf  # noqa: E402  (closed ERROR_CLASSES set — F5)

with tempfile.TemporaryDirectory() as td:
    runs = Path(td) / "runs"
    runs.mkdir()
    dp = dead_pid()
    gbyid = {n["id"]: n for n in GRAPH["nodes"]}

    # ---- F5: error_class is a member of the closed wf.ERROR_CLASSES set
    rf5 = mk_run(runs, "f5-class", GRAPH, base_nodes(dp))
    (rf5 / "wf.pid").write_text(str(dp) + "\n")
    lr.finalize_run(rf5)
    ec = json.loads((rf5 / "nodes" / "build.json").read_text()).get("error_class")
    check("F5 finalize error_class is in wf.ERROR_CLASSES", ec in wf.ERROR_CLASSES, ec)

    # ---- F3: a LEGACY (pre-efp) claim on an AMENDED graph must never be
    # stamped with the current graph's fingerprint (that fabricates a current
    # failed commit for a node it never ran). It stays stale => pending.
    OLD = {"name": "legacy", "nodes": [{"id": "build", "type": "agent", "goal": "OLD goal"}]}
    NEW = {"name": "legacy", "nodes": [{"id": "build", "type": "agent", "goal": "AMENDED goal"}]}
    rf3 = runs / "f3-legacy"
    (rf3 / "nodes").mkdir(parents=True)
    (rf3 / "graph.json").write_text(json.dumps(NEW))
    (rf3 / "nodes" / "build.json").write_text(json.dumps({
        "status": "running", "pid": dp, "skey": "wf:legacy:build:0000.0001", "attempt": 0,
        "def_hash": wc.def_hash(OLD["nodes"][0])}))
    (rf3 / "wf.pid").write_text(str(dp) + "\n")
    lr.finalize_run(rf3)
    rec3 = json.loads((rf3 / "nodes" / "build.json").read_text())
    check("F3 legacy claim finalized", rec3.get("finalized") == "dead-on-arrival", rec3)
    check("F3 legacy claim NOT stamped with the current efp", "efp" not in rec3, rec3)
    nb = {n["id"]: n for n in NEW["nodes"]}
    st3, _ = wc.node_rec(rf3, NEW["nodes"][0], nb)
    check("F3 amended legacy claim reads pending (stale), never a current failed commit",
          st3 == "pending", st3)
    check("F3 run still reads terminal via the recognized verdict",
          (wc.run_state(rf3) or {}).get("status") == "failed", (wc.run_state(rf3) or {}).get("status"))

    # ---- F4: a failed runner_exit write is NOT swallowed (nonzero exit), and
    # a retry once the dir is writable REPAIRS the missing verdict.
    rf4 = mk_run(runs, "f4-exitfail", GRAPH, base_nodes(dp))
    (rf4 / "wf.pid").write_text(str(dp) + "\n")
    (rf4 / "runner_exit.json").mkdir()          # replace() onto a dir => OSError
    rc4 = lr.finalize_run(rf4)
    check("F4 unwritable runner_exit => nonzero exit", rc4 not in (0, None), f"rc={rc4}")
    (rf4 / "runner_exit.json").rmdir()
    rc4b = lr.finalize_run(rf4)
    rx4 = wc.jload(rf4 / "runner_exit.json")
    check("F4 retry exits 0", rc4b == 0, f"rc={rc4b}")
    check("F4 retry repairs the missing verdict",
          isinstance(rx4, dict) and str(rx4.get("reason", "")).startswith("blocked by failed "), rx4)
    check("F4 no tmp litter left by the failed write",
          not list(rf4.glob("runner_exit.json.*.tmp")), list(rf4.glob("runner_exit.json.*.tmp")))

    # ---- F2: check-and-write runs UNDER the runner flock. A runner admitted
    # between the liveness check and the write (simulated: a subprocess doing
    # acquire_lock's LOCK_EX|LOCK_NB, then save_node-style done commit) must
    # never have its done commit overwritten with failed.
    rf2 = mk_run(runs, "f2-race", GRAPH, base_nodes(dp))
    (rf2 / "wf.pid").write_text(str(dp) + "\n")
    done_rec = {"status": "done", "output": {"result": "late commit"},
                "efp": wc.efp(gbyid, gbyid["build"]), "fp_rule_version": wc.FP_RULE_VERSION}
    racer = (
        "import fcntl, json, os, sys\n"
        "r = sys.argv[1]\n"
        "fd = os.open(os.path.join(r, 'runner.lock'), os.O_CREAT | os.O_RDWR, 0o644)\n"
        "try:\n"
        "    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "except OSError:\n"
        "    print('BUSY'); sys.exit(0)\n"
        "p = os.path.join(r, 'nodes', 'build.json')\n"
        "open(p + '.racer.tmp', 'w').write(sys.argv[2])\n"
        "os.replace(p + '.racer.tmp', p)\n"
        "print('COMMITTED')\n")
    outcome = {}
    real_verify = wc._verify_spawn_rec

    def racing_verify(r_, n_, byid_, rec_):
        if n_.get("id") == "build" and "racer" not in outcome:
            outcome["racer"] = subprocess.run(
                [sys.executable, "-c", racer, str(r_), json.dumps(done_rec)],
                capture_output=True, text=True, timeout=30).stdout.strip()
        return real_verify(r_, n_, byid_, rec_)

    wc._verify_spawn_rec = racing_verify
    try:
        rc2 = lr.finalize_run(rf2)
    finally:
        wc._verify_spawn_rec = real_verify
    final2 = json.loads((rf2 / "nodes" / "build.json").read_text())
    check("F2 racer ran inside the check-and-write window", outcome.get("racer") in ("BUSY", "COMMITTED"),
          outcome)
    check("F2 a runner's done commit is never overwritten with failed",
          not (outcome.get("racer") == "COMMITTED" and final2.get("status") != "done"),
          {"racer": outcome.get("racer"), "final": final2.get("status")})
    check("F2 finalize holds runner.lock: a would-be runner is refused admission (BUSY)",
          outcome.get("racer") == "BUSY", outcome)

print()
print(f"{checks} checks, {failures} failure(s)")
sys.exit(1 if failures else 0)
