#!/usr/bin/env python3
"""#61b — the four adversarial blockers, RED first, standalone (not pytest).

Evidence: adversarial review of the #61 candidate (hostile suite 10/46 FAILED;
issue #61 findings comment 5912609019). Every blocker below was REPRODUCED by
the reviewer with real processes before this file existed; this file pins each
repro as a regression check — the forge below is the reviewer's forge_child
shape (double-fork + setsid, journaling prior spawns).

 B1  recursive/detached descendants escape accounting: a double-fork
     (+setsid) grandchild that reparents before exit must still be FOUND
     (recursive subtree walk while both generations are attached — direct
     PPid sampling misses it), counted at judgment, killed before commit,
     and dead at every respawn instant of a retry ladder. The tracked set
     persists across retries (meta, per node+index): an overlap retry
     re-adopts prior-generation pids — each tracked pid is re-reached
     through its process GROUP (membership survives reparenting) — and can
     therefore never under-count.
 B2  unreadable /proc FAILS CLOSED: a probe that cannot read /proc reports
     unsafe/unknown — never safe/empty (same fail-closed family as the
     door's #25/#26 alive-proof gates). _account_tree / _isolate_prior /
     _final_quiesce all return typed left_live_descendants verdicts when
     /proc exists but cannot be listed; a machine with NO procfs at all
     keeps the honest-empty degradation (macOS/BSD).
 B3  solo partial events carry the class: when the tracked tree set was
     non-empty and the node commits `partial`, node.finished must carry
     error_class=left_live_descendants in events.jsonl. Adding this
     previously-absent field is permitted ONLY on that path; dead-or-empty
     solo events/records stay byte-identical (golden-solo EMPTY-diff gate).
 B4  adopted-child completeness: a quiet adopted child (graph-discovered
     orphan) that returns a fenced answer while its own tree outlives it
     must never commit a clean `done` — the completeness ERROR is retained
     together with (or instead of) done: partial +
     error_class=left_live_descendants with the answer and the dead-tree
     proof, at the adoption site AND the commit edge.

Run: PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_proctree_61b.py
"""
import json, os, shutil, subprocess, sys, threading, time
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BUILD = Path(os.environ.get("WF_TEST_BUILD") or HERE.parent)
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402
from wf_test_markers import read_pid_marker   # est-jue3: one parseable-content wait family (the #267 shape, shared)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " + label + (f"  {detail}" if detail else "")))
    if not cond:
        ok = False

HOME = BUILD / "home-pt61b"
RUNS = HOME / "workflows"
GC_PIDS = HOME / "gc_pids.txt"
SPAWNS = HOME / "spawns.jsonl"
FORGE = HOME / "forge_61b.py"

ALL_GC = []            # every fixture pid we ever forge; finally-block proves dead

def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        st = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return not st.startswith("Z")

def remember(pids):
    ALL_GC.extend([p for p in pids if isinstance(p, int)])

# est-gzmm (#267): the parseable-content gate now lives in wf_test_markers.py
# (est-jue3) so sibling fixtures (#61 U2, wfpid_owner_8, failures_0923) reuse
# THIS shape instead of hand-rolling existence-only waits. Import above.
def cleanup():
    for p in ALL_GC:
        if alive(p):
            try:
                os.kill(p, 9)
            except ProcessLookupError:
                pass
    t = time.time() + 4
    while any(alive(p) for p in ALL_GC) and time.time() < t:
        time.sleep(0.02)
    check("review fixtures proven dead", not any(alive(p) for p in ALL_GC),
          str([p for p in ALL_GC if alive(p)]))

def mk(run_id, nodes, **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    m = {"duckwork_bin": str(HERE / "fake"), "concurrency": 2, "node_timeout": 30,
         "retry_backoff": [0.05, 0.05], "retry_budget": 10,
         "proctree_hold_s": 0.3, "proctree_kill_proof_s": 4.0}
    m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wfrun(run_id, extra_env=None, timeout=180):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               FAKE_LOG=str(HOME / "fake.log"), FAKE_GC_PIDS=str(GC_PIDS),
               FAKE_SPAWNS_LOG=str(SPAWNS), **(extra_env or {}))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def rec_of(r, nid):
    return json.loads((r / "nodes" / f"{nid}.json").read_text())

def events(r):
    return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]

def read_rows(p):
    try:
        return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
    except OSError:
        return []

# The reviewer's forge as a duckwork_bin stand-in: goal marker ESC61B:<mode>.
# escape-progress / escape-answer / escape-transport double-fork a survivor
# that setsid()s OUT of the spawn's group, journals its pid to $FAKE_GC_PIDS
# and (per spawn) {pid, prior_alive} to $FAKE_SPAWNS_LOG — prior_alive is
# measured at the SPAWN instant, so it proves what the runner left behind.
FORGE_SRC = '''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
q = open(args[args.index("--query-file") + 1]).read()
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(q.splitlines()[0] + "\\n")
mode = q.split("ESC61B:", 1)[1].split()[0]
def _alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False
if "--continue" in args:                       # Q4-gate row: api_calls==0 (transport eligibility)
    title = args[args.index("--continue") + 1]
    import sqlite3
    c = sqlite3.connect(os.path.join(os.environ["DUCKWORK_HOME"], "state.db"))
    c.execute("create table if not exists sessions (id text primary key, title text, model text, billing_provider text, input_tokens int, output_tokens int, "
              "cache_read_tokens int, reasoning_tokens int, api_call_count int, tool_call_count int, estimated_cost_usd real, "
              "last_activity_at real, last_activity_description text, ended_at real, started_at real)")
    t = time.time()
    c.execute("insert or replace into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("f-" + title, title, "fake", "fake-provider", 0, 0, 0, 0, 0, 0, 0.0, t, "", t, t))
    c.commit(); c.close()
gcp = os.environ.get("FAKE_GC_PIDS")
prior = []
if gcp and Path(gcp).exists():
    for l in Path(gcp).read_text().splitlines():
        if l.strip() and _alive(int(l)):
            prior.append(int(l))
if os.environ.get("FAKE_SPAWNS_LOG"):
    with open(os.environ["FAKE_SPAWNS_LOG"], "a") as f:
        f.write(json.dumps({"pid": os.getpid(), "mode": mode, "prior_alive": prior}) + "\\n")
        f.flush(); os.fsync(f.fileno())
first = os.fork()
if first == 0:
    if mode.startswith("escape"):
        os.setsid()
    second = os.fork()
    if second == 0:
        if gcp:
            with open(gcp, "a") as f:
                f.write(str(os.getpid()) + "\\n"); f.flush(); os.fsync(f.fileno())
        null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(null, fd)
        if null > 2:
            os.close(null)
        time.sleep(120)
        os._exit(0)
    time.sleep(0.9)      # both generations attached long enough to be sampled
    os._exit(0)
time.sleep(1.6)
os.waitpid(first, 0)
if mode.endswith("transport"):
    print("Warning: Unknown toolsets: bogus")
    print("duckwork -z: agent failed: openai.APIConnectionError. Connection error.")
    sys.exit(2)
if mode.endswith("answer"):
    print(\'```json\\n{"ok": true, "result": "claimed green"}\\n```\', flush=True)
else:
    print("Suite is running. Waiting for the actual exit.", flush=True)
sys.exit(0)
'''

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")
FORGE.write_text(FORGE_SRC)
FORGE.chmod(0o755)

try:
    # ================= B1: recursive/detached descendants ====================
    # B1a — while BOTH generations are attached, the watch must see the
    # grandchild, not only the direct child (adversary walk-probe repro:
    # root -> intermediary -> grandchild, tree_seen=[intermediary] = RED).
    gc_marker = HOME / "b1a_gc.jsonl"
    kid_marker = HOME / "b1a_kid.txt"
    kid_src = (
        "import os,sys,time\n"
        "from pathlib import Path\n"
        f"Path(r'{kid_marker}').write_text(str(os.getpid()))\n"
        "first=os.fork()\n"
        "if first==0:\n"
        "    os.setsid()\n"
        "    second=os.fork()\n"
        "    if second==0:\n"
        f"        open(r'{gc_marker}','a').write(str(os.getpid())+'\\n'); "
        "import time as t; t.sleep(300); os._exit(0)\n"
        "    t0=time.time()\n"
        "    while not Path(sys.argv[1]).exists() and time.time()-t0<5: time.sleep(0.02)\n"
        "    time.sleep(0.9)\n"        # stay attached long to be sampled
        "    os._exit(0)\n"
        "time.sleep(3)\n"
    )
    kf = HOME / "b1a_kid.py"; kf.write_text(kid_src)
    kid_proc = subprocess.Popen([sys.executable, str(kf), str(gc_marker)],
                                start_new_session=True)   # mirrors run_child's spawn contract
    kid = read_pid_marker(kid_marker)[0]
    gc_a = read_pid_marker(gc_marker)[0]
    remember([kid, gc_a])
    snap = wf._proc_snapshot()
    attached = gc_a in snap and kid in snap        # fixture sanity: BOTH generations observable
    seen = set()
    wf._tree_watch(kid_proc, seen)
    check("B1a recursive walk FINDS the attached double-fork grandchild",
          attached and gc_a in seen, f"kid={kid} gc={gc_a} seen={sorted(seen)}")
    kid_proc.wait(timeout=30)

    # B1b..B1d — end-to-end escape runs through the real runner (forge bin).
    def escape_case(run_id, mode):
        GC_PIDS.write_text(""); SPAWNS.write_text(""); (HOME / "fake.log").write_text("")
        r = mk(run_id, [{"id": "s", "type": "agent", "goal": f"ESC61B:{mode} {run_id}"}],
               duckwork_bin=str(FORGE))
        wfrun(run_id)
        rec = rec_of(r, "s")
        gcs = [int(x) for x in GC_PIDS.read_text().split() if x.strip()]
        remember(gcs)
        spawns = read_rows(SPAWNS)
        n_spawns = (HOME / "fake.log").read_text().count(run_id)
        return r, rec, gcs, spawns, n_spawns

    r, rec, gcs, spawns, n_spawns = escape_case("pt61b-ep", "escape-progress")
    check("B1b escape-progress caught by the completeness gate (one spawn, typed failed)",
          rec.get("status") == "failed"
          and rec.get("error_class") == "left_live_descendants" and n_spawns == 1,
          json.dumps({k: rec.get(k) for k in ("status", "error_class")}) + f" spawns={n_spawns}")
    check("B1b escape-progress the REAL escapee is accounted (tree_descendants)",
          bool(gcs) and all(g in (rec.get("tree_descendants") or []) for g in gcs),
          f"gcs={gcs} rec_td={rec.get('tree_descendants')}")
    evs = events(r)
    check("B1b escape-progress typed error persisted in events.jsonl",
          any(e.get("error_class") == "left_live_descendants" for e in evs),
          str([(e.get("event"), e.get("error_class")) for e in evs])[:300])
    check("B1b escape-progress ALL actual descendants dead before commit",
          bool(gcs) and not any(alive(g) for g in gcs),
          f"alive={[g for g in gcs if alive(g)]}")

    r, rec, gcs, spawns, n_spawns = escape_case("pt61b-ea", "escape-answer")
    check("B1c escape-answer commits partial (never done) with the class",
          rec.get("status") == "partial"
          and rec.get("error_class") == "left_live_descendants",
          json.dumps({k: rec.get(k) for k in ("status", "error_class")}))
    check("B1c escape-answer ALL actual descendants dead before commit",
          bool(gcs) and not any(alive(g) for g in gcs),
          f"alive={[g for g in gcs if alive(g)]}")

    r, rec, gcs, spawns, n_spawns = escape_case("pt61b-et", "escape-transport")
    check("B1d escape-transport prior tree dead at EVERY respawn instant",
          len(spawns) == 3 and all(not s.get("prior_alive") for s in spawns),
          f"spawns={[{k: s.get(k) for k in ('pid', 'prior_alive')} for s in spawns]}")
    check("B1d escape-transport ALL actual descendants dead at run end",
          bool(gcs) and not any(alive(g) for g in gcs),
          f"alive={[g for g in gcs if alive(g)]}")

    # B1e — overlap retry re-adopts the tracked set: a second judgment whose
    # OWN sampling is empty must still account (and kill) the pids tracked by
    # an earlier attempt — persist the tracked set, never under-count.
    overlap = subprocess.Popen([sys.executable, "-c",
                                "import os,time; os.setsid(); time.sleep(300)"],
                               start_new_session=False)   # own session: only killable via the tracked pid
    remember([overlap.pid])
    dead_spawn = subprocess.Popen([sys.executable, "-c", "pass"]); dead_spawn.wait()
    meta = {"_run": HOME, "_proctree_tracked": {("n61b", None): {overlap.pid}}}
    verdict = wf._account_tree(meta, {"id": "n61b"}, None, 9, dead_spawn.pid, set(), False)
    check("B1e a judgment with empty own-sampling RE-ADOPTS the persisted tracked set",
          verdict is not None and verdict[0] == "failed"
          and overlap.pid in (verdict[1].get("tree_descendants") or []),
          json.dumps({"kind": verdict[0] if verdict else None,
                      "td": (verdict[1] or {}).get("tree_descendants") if verdict else None})[:300])
    check("B1e the re-adopted tracked pid is proven dead", not alive(overlap.pid),
          f"pid={overlap.pid}")

    # ================= B2: unreadable /proc FAILS CLOSED =====================
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                         start_new_session=True)
    remember([p.pid])
    run2 = HOME / "proc-denied"; run2.mkdir(exist_ok=True)
    real_listdir = wf.os.listdir

    def unreadable(path):
        if str(path) == "/proc":
            raise PermissionError("test fault injection: proc listing denied")
        return real_listdir(path)

    def missing_procfs(path):
        if str(path) == "/proc":
            raise FileNotFoundError(str(path))     # /proc absent entirely (macOS/BSD)
        return real_listdir(path)

    with patch.object(wf.os, "listdir", missing_procfs):
        snap = wf._proc_snapshot()      # no procfs at all: honest empty, not a raise
    check("B2 NO-procfs machines keep the honest-empty degradation (no raise)",
          snap == {}, f"type={type(snap).__name__} value={snap!r}")
    with patch.object(wf.os, "listdir", unreadable):
        verdict = wf._account_tree({"_run": run2}, {"id": "s"}, None, 0, p.pid, set(), False)
        isolate = wf._isolate_prior({"_run": run2}, {"pid": p.pid}, "node", {"node": "s"})
        fin = wf._final_quiesce({"_run": run2},
                                {"status": "done", "output": {}, "pid": p.pid},
                                "node", {"node": "s"})
    check("B2 unreadable /proc FAILS CLOSED — account_tree/isolate_prior/final_quiesce unsafe, never empty",
          verdict is not None and isolate is not None
          and fin.get("status") == "failed"
          and fin.get("error_class") == "left_live_descendants",
          json.dumps({"account": (verdict[0] if verdict else None),
                      "isolate": bool(isolate), "final": fin.get("error_class"),
                      "final_class": fin.get("error_class")}))
    check("B2 the real live fixture was NEVER reported safe/empty", alive(p.pid),
          f"pid={p.pid}")
    try:
        os.kill(p.pid, 9)
    except ProcessLookupError:
        pass
    p.wait()

    # ================= B3: solo partial EVENT carries the class ==============
    # The record side was proven in B1c; the EVENT side is the blocker
    # (tree_kill + node.finished both omitted it on the candidate).
    r, rec, gcs, spawns, n_spawns = escape_case("pt61b-solo-ev", "escape-answer")
    evs = events(r)
    check("B3 solo partial node.finished carries error_class=left_live_descendants",
          rec.get("status") == "partial"
          and any(e.get("event") == "node.finished"
                  and e.get("error_class") == "left_live_descendants" for e in evs),
          str([(e.get("event"), e.get("error_class")) for e in evs])[:400])
    # byte-identity on the unchanged path: healthy solo keeps NO new fields
    (HOME / "fake.log").write_text("")
    r = mk("pt61b-ok", [{"id": "h", "type": "agent", "goal": 'pt61b-ok JSON:{"result":"ok"}'}])
    wfrun("pt61b-ok")
    rec = rec_of(r, "h")
    evs = events(r)
    fin = [e for e in evs if e.get("event") == "node.finished"]
    check("B3 healthy solo stays byte-identical: no tree_* keys, no error_class on finished",
          rec.get("status") == "done" and not any(k.startswith("tree_") for k in rec)
          and fin and all("error_class" not in e for e in fin),
          json.dumps({"keys": sorted(rec), "finished_keys": sorted(fin[0]) if fin else []})[:400])

    # ================= B4: adopted-child completeness ========================
    # Graph-discovered adoption sibling (adversary adopt-probe repro): the
    # adopted child returns a fenced answer while its own tree stays alive.
    D = HOME / "adopt-probe"; (D / "nodes").mkdir(parents=True)
    log = D / "adopt.a0.log"; marker = D / "grandchild.pid"
    source = ("import os,time,sys\nfrom pathlib import Path\n"
              "p=os.fork()\n"
              "if p==0:\n"
              f"    Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(120); os._exit(0)\n"
              "time.sleep(1); print('```json\\n{\"result\":\"claimed complete\"}\\n```',flush=True)\n")
    with log.open("w") as f:
        ap = subprocess.Popen([sys.executable, "-c", source, str(marker), "wf:adopt-fixture"],
                              stdout=f, stderr=f, start_new_session=True)
    ameta = {"_run": D, "_procs": {}, "_procs_lock": threading.Lock(),
             "_stop": threading.Event(), "proctree_hold_s": 0.0, "proctree_kill_proof_s": 2}
    # est-gzmm: wait for the PARSEABLE pid, not mere file existence — existence
    # fires at open() and the grandchild may not be resident yet when adoption walks.
    gc_b4 = read_pid_marker(marker, timeout=15)[0]
    rec = wf._adopt_child(ameta, {"id": "fan"}, {"fan": {"id": "fan"}}, 0,
                          {"pid": ap.pid, "log_path": str(log), "skey": "wf:adopt-fixture",
                           "started": wf.now(), "attempt": 0}, None)
    try:
        ap.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    remember([ap.pid, gc_b4])
    # The survivor (120 s sleep) outlived the child (~1 s) across the verdict.
    # After the fix the adoption site may already have killed it — the honest
    # evidence is then the runner's OWN record (tree_descendants + proven dead);
    # before the fix it is simply still alive (that is the blocker).
    check("B4 the fixture really left a surviving tree across the adoption verdict",
          gc_b4 is not None and (alive(gc_b4)
                                 or gc_b4 in (rec.get("tree_descendants") or [])),
          f"gc={gc_b4} alive={gc_b4 is not None and alive(gc_b4)} "
          f"rec_td={rec.get('tree_descendants')}")
    fin = wf._final_quiesce(ameta, rec, "item", {"node": "fan", "index": 0})
    check("B4 quiet adopted child with live tree NEVER commits a clean done",
          fin.get("status") == "partial"
          and fin.get("error_class") == "left_live_descendants",
          json.dumps({"adopted": rec.get("status"), "final": fin.get("status"),
                      "class": fin.get("error_class")}))
    check("B4 the completeness ERROR is retained together with the answer, tree proven dead",
          fin.get("output") == {"result": "claimed complete"}
          and fin.get("tree_proof") == "dead"
          and not (gc_b4 is not None and alive(gc_b4)),
          json.dumps({"output": fin.get("output"), "tree_proof": fin.get("tree_proof"),
                      "gc_alive": gc_b4 is not None and alive(gc_b4)}))
    # the harvest-ONCE memo must have stored the SAME honest verdict (#61b B4)
    memo = (ameta.get("_adopt_result") or {}).get(f"fan:0:{ap.pid}")
    check("B4 the adoption memo caches the honest verdict, never a clean done",
          memo is not None and memo.get("status") == "partial"
          and memo.get("error_class") == "left_live_descendants",
          json.dumps({k: (memo or {}).get(k) for k in ("status", "error_class")}))
finally:
    cleanup()

print("DONE" if ok else "FAILED")
sys.exit(0 if ok else 1)
