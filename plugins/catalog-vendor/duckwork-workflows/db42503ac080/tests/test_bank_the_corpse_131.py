#!/usr/bin/env python3
"""#131 — bank-the-corpse on wall-kill.

A child killed at its wall (`timeout`) used to leave its work only in the
durable work dir, with the integrator hand-banking each dead lane. Now the
runner deterministically writes `nodes/<node>[.<i>].corpus/` on EVERY wall-kill
(both wait paths: the spawn path in run_child and the adopted-orphan path in
_adopt_child): `work/` (snapshot of the child's durable work dir), `stdout_tail.txt`
(last 4000 chars of the capture) and `manifest.json` (every file with size +
mtime, newest first; `last_written` = the newest). One `node.banked` event, and a
`banked` pointer on the timed-out death record.

  N  spawn path: a stub child writes two files, prints, then sleeps past its wall
     -> corpus contents, manifest last_written, one node.banked line, verdict
     unchanged (failed/timeout), record carries banked.
  F  fan-out item: the committed per-item record carries the same pointer.
  H  healthy spawn: no corpus, no node.banked, no `banked` key (byte-identity law).
  E  OSError (a regular file squats on the corpus path): honest-empty — node.banked
     with error=, files=0, no pointer, verdict still failed/timeout, squatter intact.
  U  OSError inside the copy (in-process): the helper never raises, returns None.
  A  adopted path: an orphan past its re-armed wall is killed and banked the same way.
  N1 per-file sizes match the banked snapshot after source growth and truncation.
  N2 failed source/destination opens are honest-empty and release acquired handles.
  N3 PROVENANCE evidence counts match the runtime check ledger (including itself).

Run: python3 tests/test_bank_the_corpse_131.py
"""
import json, os, re, shutil, subprocess, sys, tempfile, threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BUILD = Path(os.environ.get("WF_TEST_BUILD") or HERE.parent)
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402

ok, checks = True, []
def check(label, cond, detail=""):
    global ok
    checks.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and bool(cond)

HOME = Path(tempfile.mkdtemp(prefix="wf-bank131-"))
RUNS = HOME / "workflows"
RUNS.mkdir()
STUB = HOME / "stub_corpse.py"
STUB.write_text(f"#!{sys.executable}\n" + r'''
import json, os, sys, time
a = sys.argv[1:]
if "--query-file" not in a:
    sys.exit(0)
q = open(a[a.index("--query-file") + 1]).read()
if "HEALTHY131" in q:
    print("```json\n" + json.dumps({"result": "ok"}) + "\n```", flush=True)
    sys.exit(0)
open("first.txt", "w").write("first banked line\n")
time.sleep(0.3)
os.makedirs("sub", exist_ok=True)
open("sub/second.txt", "w").write("second, the newest write\n")
print("CORPSE131 stdout tail marker", flush=True)
time.sleep(60)
''')
STUB.chmod(0o755)

def mk(run_id, nodes):
    r = RUNS / run_id
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": str(STUB), "concurrency": 1,
                                            "node_timeout": 30}))
    return r

def wfrun(run_id):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id], env=env,
                          capture_output=True, text=True, timeout=120).stdout.strip()

def rec_of(r, name):
    return json.loads((r / "nodes" / f"{name}.json").read_text())

def banked(r):
    return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()
            if json.loads(l).get("event") == "node.banked"]

try:
    # ============ N: spawn-path wall-kill banks the corpse ============
    r = mk("b131-wall", [{"id": "w", "type": "agent", "goal": "wall-kill me", "timeout": 2}])
    out = wfrun("b131-wall")
    rec, corpus = rec_of(r, "w"), r / "nodes" / "w.corpus"
    check("N verdict unchanged: failed / timeout",
          rec.get("status") == "failed" and rec.get("error_class") == "timeout",
          json.dumps({k: rec.get(k) for k in ("status", "error_class", "error")}) + out[-200:])
    check("N death record carries the banked pointer",
          rec.get("banked") == str(corpus) and corpus.is_dir(), str(rec.get("banked")))
    check("N work dir snapshotted (both files, nested path kept)",
          (corpus / "work" / "first.txt").read_text() == "first banked line\n"
          and (corpus / "work" / "sub" / "second.txt").read_text() == "second, the newest write\n"
          if corpus.is_dir() else False)
    tail = (corpus / "stdout_tail.txt").read_text() if corpus.is_dir() else ""
    check("N stdout_tail.txt holds the capture tail", "CORPSE131" in tail and len(tail) <= 4000)
    man = json.loads((corpus / "manifest.json").read_text()) if corpus.is_dir() else {}
    rows = man.get("files") or []
    check("N manifest last_written = newest-mtime file",
          man.get("last_written") == "sub/second.txt", str(man.get("last_written")))
    check("N manifest lists files newest-first with sizes + mtimes",
          [x.get("path") for x in rows] == ["sub/second.txt", "first.txt"]
          and [x.get("size") for x in rows] == [25, 18]
          and all(isinstance(x.get("mtime"), float) for x in rows), str(rows)[:300])
    bk = banked(r)
    check("N exactly one node.banked line with node/index/spawn/files/bytes/corpus",
          len(bk) == 1 and bk[0].get("node") == "w" and bk[0].get("index") is None
          and isinstance(bk[0].get("spawn"), int) and bk[0].get("files") == 2
          and bk[0].get("bytes") == 43 and bk[0].get("corpus") == str(corpus)
          and "error" not in bk[0], str(bk)[:300])

    # ============ F: a fan-out item's committed record carries the pointer too ============
    r = mk("b131-fan", [{"id": "fan", "type": "agent", "timeout": 2,
                         "fanout": {"items": ["x"], "goal": "wall-kill item {index}"}}])
    wfrun("b131-fan")
    rec, corpus = rec_of(r, "fan.0"), r / "nodes" / "fan.0.corpus"
    check("F item record: timeout verdict + banked pointer to fan.0.corpus",
          rec.get("error_class") == "timeout" and rec.get("banked") == str(corpus)
          and (corpus / "work" / "first.txt").is_file(),
          json.dumps({k: rec.get(k) for k in ("status", "error_class", "banked")}))

    # ============ H: healthy spawn stays byte-identical ============
    r = mk("b131-ok", [{"id": "h", "type": "agent", "goal": "HEALTHY131 answer"}])
    wfrun("b131-ok")
    rec = rec_of(r, "h")
    check("H healthy node done, no banked key, no corpus, no node.banked",
          rec.get("status") == "done" and "banked" not in rec
          and not list((r / "nodes").glob("*.corpus")) and banked(r) == [],
          json.dumps(rec)[:200])

    # ============ E: OSError on the bank -> honest-empty, verdict untouched ============
    r = mk("b131-oserr", [{"id": "w", "type": "agent", "goal": "wall-kill me", "timeout": 2}])
    squat = r / "nodes" / "w.corpus"
    squat.write_text("not a dir")
    wfrun("b131-oserr")
    rec, bk = rec_of(r, "w"), banked(r)
    check("E verdict unchanged by a failed bank",
          rec.get("status") == "failed" and rec.get("error_class") == "timeout",
          json.dumps({k: rec.get(k) for k in ("status", "error_class")}))
    check("E honest-empty: one node.banked with error=, files=0, no pointer",
          len(bk) == 1 and bk[0].get("error") and bk[0].get("files") == 0
          and bk[0].get("bytes") == 0 and bk[0].get("corpus") is None
          and "banked" not in rec, str(bk)[:300])
    check("E squatter untouched, no tmp left behind",
          squat.read_text() == "not a dir"
          and not [p for p in (r / "nodes").iterdir() if ".tmp" in p.name])

    # ============ U: OSError mid-copy never escapes the helper ============
    # est-muob D1 made the snapshot a bounded read-loop, so the mid-copy seam
    # is now shutil.copystat (inside the same protected region copy2 used to
    # sit in) — the law under test is unchanged: OSError mid-copy => honest-
    # empty, helper returns None and never raises.
    r = mk("b131-unit", [{"id": "u", "type": "agent", "goal": "x"}])
    (wf.child_work_dir(r, {"id": "u"}, None) / "f.txt").write_text("x")
    real = shutil.copystat
    def _boom(*a, **k): raise PermissionError("injected")
    shutil.copystat = _boom
    try:
        got = wf._bank_the_corpse(r, {"id": "u"}, None, 0, "tail")
        raised = None
    except Exception as e:   # noqa: BLE001 — the law under test is "never raises"
        got, raised = None, e
    finally:
        shutil.copystat = real
    check("U helper returns None and never raises on a mid-copy OSError",
          got is None and raised is None and banked(r)[-1:] and "injected" in banked(r)[-1]["error"],
          repr(raised))

    # N2: either open can fail; the second open must not leak the first handle.
    open_results = []
    for fail_mode in ("rb", "wb"):
        r = mk("b131-open-" + fail_mode, [{"id": "o", "type": "agent", "goal": "x"}])
        node = {"id": "o"}
        (wf.child_work_dir(r, node, None) / "open.txt").write_text("snapshot")
        handles, modes = [], []
        def fail_open(file, mode, *args, **kwargs):
            if mode not in ("rb", "wb"):
                return open(file, mode, *args, **kwargs)
            modes.append(mode)
            if mode == fail_mode:
                raise PermissionError("injected " + mode + " open")
            handle = open(file, mode, *args, **kwargs)
            handles.append(handle)
            return handle
        raised = None
        try:
            with patch.object(wf, "open", fail_open, create=True):
                got = wf._bank_the_corpse(r, node, None, 0, "tail")
        except Exception as exc:
            got, raised = None, exc
        events = banked(r)
        closed = all(handle.closed for handle in handles)
        open_results.append({"mode": fail_mode, "closed": closed,
                             "ok": got is None and raised is None and closed
                             and modes == (["rb"] if fail_mode == "rb" else ["rb", "wb"])
                             and len(events) == 1 and events[0].get("corpus") is None
                             and events[0].get("files") == events[0].get("bytes") == 0
                             and "injected " + fail_mode + " open" in events[0].get("error", "")
                             and not list((r / "nodes").glob("*.tmp"))
                             and not list((r / "nodes").glob("*.corpus"))})
        for handle in handles:
            handle.close()  # also clean up the deliberately broken implementation
    check("N2 both failing opens are honest-empty and close every acquired handle",
          all(result["ok"] for result in open_results), str(open_results))

    # ============ A: adopted-orphan path banks the same way ============
    r = mk("b131-adopt", [{"id": "f", "type": "agent", "goal": "x", "timeout": 1}])
    node = {"id": "f", "type": "agent", "goal": "x", "timeout": 1}
    (wf.child_work_dir(r, node, 0) / "a.txt").write_text("adopted work\n")
    lp = r / "logs" / "f.0.a0.log"
    lp.parent.mkdir(exist_ok=True); lp.write_text("ADOPT131 tail\n")
    kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                           start_new_session=True)
    meta = {"_run": r, "_stop": threading.Event(), "_procs_lock": threading.Lock(),
            "_procs": {}, "node_timeout": 1}
    started = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
    child = {"pid": kid.pid, "log_path": str(lp), "started": started, "attempt": 0, "skey": "s#a0"}
    threading.Thread(target=kid.wait, daemon=True).start()   # reap: zombie = dead
    res = wf._adopt_child(meta, node, {"f": node}, 0, child, None)
    corpus = r / "nodes" / "f.0.corpus"
    man = json.loads((corpus / "manifest.json").read_text()) if corpus.is_dir() else {}
    bk = banked(r)
    check("A adopted wall-kill: verdict timeout + banked pointer",
          res.get("error_class") == "timeout" and res.get("banked") == str(corpus),
          json.dumps({k: res.get(k) for k in ("status", "error_class", "banked")}))
    check("A corpus: work snapshot + stdout tail + manifest",
          corpus.is_dir() and (corpus / "work" / "a.txt").read_text() == "adopted work\n"
          and "ADOPT131" in (corpus / "stdout_tail.txt").read_text()
          and man.get("last_written") == "a.txt")
    check("A one node.banked line (index=0, spawn=0)",
          len(bk) == 1 and bk[0].get("index") == 0 and bk[0].get("spawn") == 0
          and bk[0].get("files") == 1, str(bk)[:300])

    # ============ D1 (est-muob): the cap is decided AT COPY TIME, honestly ============
    # Deep-review/adversary probe: the 16 MiB budget is checked against a stat
    # taken BEFORE the copy; an external writer that grows the file in that
    # window lands 17+ MiB on disk while the manifest reports 1024 bytes. The
    # snapshot copy must be byte-bounded (never more than the budget on disk)
    # and the manifest must report the ACTUAL copied bytes + a truncated flag.
    r = mk("b131-grow", [{"id": "g", "type": "agent", "goal": "x"}])
    node = {"id": "g"}
    wd = wf.child_work_dir(r, node, None)
    wd.mkdir(parents=True, exist_ok=True)
    gf = wd / "growing.bin"
    gf.write_bytes(b"x" * 1024)
    real_copy2 = shutil.copy2
    grew = []
    def grow_then_copy(src, dst, *a, **k):
        # Deterministic interleaving: external writer lands after the bank's
        # stat, before/inside the copy (mirrors the adversary probe both for
        # the copy2 path and for a bounded open()/read loop).
        if not grew:
            grew.append(1)
            with open(src, "ab") as h:
                h.write(b"z" * (17 << 20))
        return real_copy2(src, dst, *a, **k)
    real_open = open
    def grow_then_open(file, *a, **k):
        if str(file).endswith("growing.bin") and not grew:
            grew.append(1)
            with open(file, "ab") as h:
                h.write(b"z" * (17 << 20))
        return real_open(file, *a, **k)
    with patch.object(wf.shutil, "copy2", grow_then_copy), patch("builtins.open", grow_then_open):
        bank = wf._bank_the_corpse(r, node, None, 0, "tail")
    check("D1 bank succeeds despite post-stat growth", bank is not None, repr(bank))
    if bank is not None:
        on_disk = sum(f.stat().st_size for f in (Path(bank) / "work").rglob("*") if f.is_file())
        man = json.loads((Path(bank) / "manifest.json").read_text())
        check("D1 copy is byte-bounded: snapshot never exceeds the budget on disk",
              on_disk <= man["budget"], f"on_disk={on_disk} budget={man['budget']}")
        check("D1 manifest reports ACTUAL copied bytes (not the stale pre-copy stat)",
              man["bytes"] == on_disk, f"manifest={man['bytes']} on_disk={on_disk}")
        check("D1 growth that busts the budget is flagged truncated",
              man.get("truncated") is True, json.dumps({k: man.get(k) for k in ("bytes", "budget", "truncated")}))
        bk = banked(r)
        check("D1 node.banked line carries the same honest bytes",
              len(bk) == 1 and bk[0].get("bytes") == on_disk, str(bk)[:300])
    check("N1 every copied per-file size equals the banked bytes after growth/truncation",
          bank is not None and all(row["size"] == (Path(bank) / "work" / row["path"]).stat().st_size
                                   for row in man["files"] if row["copied"]),
          str(man.get("files"))[:300])

    # ============ D2 (est-muob): quarantine records keep the corpse pointer ============
    # The quarantine builders carry log_path/prompt_path/... forward but DROP
    # `banked` — a fail-closed record would point at no corpse although the
    # dead attempt's work is banked. banked must survive like log_path does.
    src_rec = {"status": "failed", "error_class": "timeout", "banked": "/tmp/x.corpus",
               "log_path": "log", "prompt_path": "p", "spawn": 0, "raw": "progress",
               "skey": "k"}
    ll = wf._left_live_record(1, [2], "probe", src_rec)
    check("D2 _left_live_record carries banked forward like log_path",
          ll.get("banked") == "/tmp/x.corpus" and ll.get("log_path") == "log",
          json.dumps({k: ll.get(k) for k in ("banked", "log_path")}))
    ur = wf._proc_unreadable_record(1, "n", 0, src_rec)
    check("D2 _proc_unreadable_record carries banked forward like log_path",
          ur.get("banked") == "/tmp/x.corpus" and ur.get("log_path") == "log",
          json.dumps({k: ur.get(k) for k in ("banked", "log_path")}))

    # ============ D3 (est-muob): a wedged events.jsonl can never move the verdict ============
    # AGENTS.md: the bank logs node.banked and NEVER raises. The success-path
    # log() sits OUTSIDE the protected try: a real events.jsonl wedge
    # (directory in its place -> IsADirectoryError) escapes as OSError into the
    # timeout verdict path. Both the success log and the honest-empty error log
    # must be unable to raise out of the helper.
    r = mk("b131-wedge", [{"id": "k", "type": "agent", "goal": "x"}])
    node = {"id": "k"}
    (wf.child_work_dir(r, node, None) / "w.txt").write_text("banked despite the wedge\n")
    er = r / "events.jsonl"
    if er.exists():
        er.unlink()
    er.mkdir()
    raised = None
    try:
        bank = wf._bank_the_corpse(r, node, None, 0, "tail")
    except OSError as e:
        bank, raised = None, e
    check("D3 success-path log wedge (events.jsonl is a dir) never raises out of the helper",
          raised is None, repr(raised))
    # error-path: bank fails (squatter) AND the honest-empty log() wedges too.
    r2 = mk("b131-wedge2", [{"id": "k", "type": "agent", "goal": "x"}])
    (r2 / "nodes" / "k.corpus").write_text("not a dir")
    er2 = r2 / "events.jsonl"
    if er2.exists():
        er2.unlink()
    er2.mkdir()
    raised2 = None
    try:
        bank2 = wf._bank_the_corpse(r2, {"id": "k"}, None, 1, "tail")
    except OSError as e:
        bank2, raised2 = None, e
    check("D3 honest-empty error log wedge never raises out of the helper",
          raised2 is None and bank2 is None, repr(raised2))

    # ============ D4 (est-muob): bounded retry keeps the corpse reference ============
    # The ordinary successful timeout -> retry re-drive drops `banked` from
    # BOTH the merged final result and the dead attempt's attempts_log entry,
    # so the winner record silently loses the pointer to the dead drive-1
    # corpse. Probe-mirrored: only progress/budget/quarantine/counters patched.
    r = mk("b131-retry", [{"id": "t", "type": "agent", "goal": "x"}])
    meta = {"_run": r, "_stop": threading.Event(), "_procs_lock": threading.Lock(),
            "_retries_left": 1}
    dead_rec = {"status": "failed", "error_class": "timeout", "banked": "/tmp/dead1.corpus",
                "log_path": "log", "spawn": 0, "raw": "progress", "skey": "k"}
    with patch.object(wf, "_tool_progress", return_value=True), \
         patch.object(wf, "_BOUNDED_RETRY_BACKOFF", 0), \
         patch.object(wf, "_isolate_prior", return_value=None), \
         patch.object(wf, "_attempt_counts", return_value={}):
        retried = wf._bounded_retry(meta, dead_rec,
                                    lambda **kw: {"status": "done", "output": {"ok": True}, "spawn": 1},
                                    "node", {"node": "t"})
    check("D4 successful re-drive keeps banked on the final result",
          retried.get("status") == "done" and retried.get("banked") == "/tmp/dead1.corpus",
          json.dumps({k: retried.get(k) for k in ("status", "banked")}))
    al = retried.get("attempts_log") or []
    check("D4 dead attempt's attempts_log entry keeps banked",
          len(al) == 1 and al[0].get("error_class") == "timeout"
          and al[0].get("banked") == "/tmp/dead1.corpus", str(al)[:300])
finally:
    shutil.rmtree(HOME, ignore_errors=True)

provenance = json.loads((BUILD / "ci-baseline" / "PROVENANCE.json").read_text())
# Once a green-CI refresh supersedes this outside-CI row, no local quote remains.
evidence = [row for row in provenance["rows_added_outside_ci"]
            if row["test"] == Path(__file__).name]
measured = evidence[0]["measured"] if len(evidence) == 1 else ""
count = re.search(r"\bTOTAL (\d+) FAIL (\d+)\b", measured)
check("N3 PROVENANCE count matches the actual runtime ledger including this check",
      not evidence or (len(evidence) == 1 and count is not None and int(count[1]) == len(checks) + 1),
      measured)
print(f"TOTAL {len(checks)} FAIL {sum(not passed for passed in checks)}")
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
