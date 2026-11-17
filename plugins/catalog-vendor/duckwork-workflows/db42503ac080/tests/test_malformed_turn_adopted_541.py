#!/usr/bin/env python3
"""est-2ek.1.541 R8 — the malformed-turn CLASSIFICATION LAW is path-invariant.

Deep-review finding (R8, verified with real-runner evidence): the fresh-head rc!=0
path typed the serialized-tool-call reply `malformed_turn` and re-drove it, while
the ADOPTED-death path (the runner was respawned and adopted the still-live child;
rc unobservable) classified the identical reply `unknown` — sibling coverage was
incomplete, so the same death produced two different classes depending on which
path reached it.

Law pinned here: the SAME reply, driven through the REAL runner on BOTH paths
(fresh spawn vs adopted live orphan), must commit the SAME error_class
(`malformed_turn`, closed-set member) and the verbatim tool-call-as-text
diagnostic. The bounded ladder may or may not re-drive (the adopted attempt's
spend is already committed) — the CLASS never varies.

Mechanics mirror the field harness: spawn tests/fake (toolcall_text_541, rc=1)
OUTSIDE the runner as a verified live orphan (start_new_session, registered via
wf.write_spawn_record + wfcommon.active_child proof), then run the real runner —
it must ADOPT rather than re-spawn, the child then dies with the markup, and the
node record must carry the class. Positive tool-progress is written by the fake's
mode itself (the same evidence the bounded gate reads).

Red-proof (run before the fix): adopted path committed error_class='unknown'
with one invocation; fresh path 'malformed_turn' with two. Green: both
'malformed_turn'.
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home541r8"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(RUNS)      # #71 subprocess form: never leak runs
sys.path.insert(0, str(BUILD))
import wf as wfmod      # noqa: E402
import wfcommon         # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " + label) + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}


def mk_run(run_id):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    node = {"id": "fan", "type": "agent", "schema": SCHEMA, "timeout": 25,
            "fanout": {"items": ["alpha"],
                       "goal": "Inspect {item} TOOLCALL541"}}
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [node]}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": FAKE, "node_timeout": 25, "concurrency": 1,
         "retry_backoff": [0.05, 0.05]}))
    return r, node


def drive(mode):
    """mode='fresh': plain run (one spawn dies with markup).
       mode='adopted': register a verified LIVE orphan first — the runner must
       adopt it and classify its death."""
    run, node = mk_run(f"r8-{mode}")
    byid = {"fan": node}
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               FAKE_LOG=str(HOME / f"fake-{mode}.log"),
               FAKE_MODE="toolcall_text_541", FAKE_RC="1", FAKE_TERN="unknown",
               FAKE_DELAY="0")            # runner's own children: die fast
    orphan_env = dict(env, FAKE_DELAY="30")   # the orphan holds; runner must adopt it
    orphan = None
    if mode == "adopted":
        skey = wfmod.skey_for(run, byid, node, 0)
        log = wfmod.spawn_log_path(run, node, 0, 0)
        env["DUCKWORK_QUIET_TURN_REPORT_FILE"] = str(
            log.with_name(log.name.replace(".log", ".turn.json")))
        qf = run / "orphan-prompt.md"
        qf.write_text("Inspect alpha TOOLCALL541\n", encoding="utf-8")
        argv = [FAKE, "chat", "--query-file", str(qf), "--continue", skey + "#a0", "-Q"]
        with log.open("w") as f:
            orphan = subprocess.Popen(argv, env=orphan_env, stdout=f, stderr=f,
                                      start_new_session=True)
        wfmod.write_spawn_record(run, node, byid, 0, 0, argv, log, orphan.pid, skey)
        # deterministic settle, mirroring the adversary probe's ready-file: the
        # fake registers its positive tool-progress row in state.db immediately
        # before its FAKE_DELAY hold — when the row exists the child is alive
        # and past sqlite setup, and active_child verification can't race.
        db = HOME / "state.db"
        deadline = time.time() + 15
        row = False
        while time.time() < deadline and not row:
            if db.exists():
                try:
                    import sqlite3
                    c = sqlite3.connect(str(db))
                    row = bool(c.execute(
                        "select 1 from sessions where title like ? and tool_call_count > 0",
                        (f"%{skey}%",)).fetchone())
                    c.close()
                except Exception:
                    row = False
            if not row:
                time.sleep(0.1)
        if not row and orphan.poll() is not None:
            print(f"fixture died early rc={orphan.returncode} log_tail="
                  f"{log.read_text()[-200:]!r}")
        verified = None
        deadline = time.time() + 10
        while time.time() < deadline:
            verified = wfcommon.active_child(run, node, byid, 0)
            if verified:
                break
            time.sleep(0.05)
        check("fixture: adopted mode had a verified live orphan", verified is not None,
              "active_child never verified the fixture")
        # the child writes its positive tool-progress row while it runs (it
        # holds via FAKE_DELAY); poll until the evidence exists.
        progress = False
        deadline = time.time() + 10
        while time.time() < deadline:
            progress = wfmod._tool_progress(run, skey, log.read_text())
            if progress:
                break
            time.sleep(0.1)
        check("fixture: orphan carried positive real tool-progress", bool(progress),
              "the death would not qualify for the bounded ladder on evidence")
        env.pop("DUCKWORK_QUIET_TURN_REPORT_FILE", None)  # the runner must not see it
    try:
        subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", str(run)],
                       env=env, capture_output=True, text=True, timeout=60)
    finally:
        if orphan is not None:
            try:
                orphan.wait(timeout=5)
            except subprocess.TimeoutExpired:
                orphan.kill()
                orphan.wait(timeout=5)
    rec = json.loads((run / "nodes" / "fan.json").read_text())
    results = (rec.get("output") or {}).get("all_results") or [rec]
    if mode == "adopted":
        evs = []
        try:
            evs = [json.loads(l) for l in (run / "events.jsonl").read_text().splitlines()]
        except FileNotFoundError:
            pass
        adopted = [e for e in evs if e.get("event") == "item.adopted"]
        # THE load-bearing assertion of this pin: if the runner re-spawned fresh
        # instead of adopting the live orphan, the death is classified by the
        # fresh path (which already carries the class) and the test proves
        # nothing about the adopted path. Fail loudly so the pin can never
        # silently degrade into a re-run of the fresh-path pin.
        check("R8 adopted: the runner ADOPTED the live orphan (item.adopted event)",
              bool(adopted), f"events={[e.get('event') for e in evs]}")
        # Committee wf166 A2: the FINAL record is replaced by the bounded
        # respawn's result (wf.py's ladder hands r2 back), so a wrong class on
        # the ADOPTED death alone can hide behind a correct fresh-path class.
        # The load-bearing fact is the RETRY EVENT for the adopted attempt: it
        # stamps the dead attempt's own error_class. With R8 removed (adopted
        # death -> transport) this check goes RED even while the final class
        # stays malformed_turn — the pin can no longer pass on the wrong path.
        retrying = [e for e in evs if str(e.get("event", "")).endswith(".retry")
                    and e.get("index") == 0]
        check("R8 adopted: the ADOPTED attempt's own death was typed malformed_turn "
              "(retry event carries the dead attempt's class, not the respawn's)",
              bool(retrying) and retrying[0].get("error_class") == "malformed_turn",
              f"retrying={[(e.get('event'), e.get('error_class')) for e in retrying]}")
        item0 = next((i for i in ((rec.get("output") or {}).get("all_results") or [])
                      if (i.get("attempts_log") or [])), None)
        al = (item0 or {}).get("attempts_log") or []
        check("R8 adopted: attempts_log[0] — the adopted generation — carries the typed class",
            bool(al) and al[0].get("error_class") == "malformed_turn",
              f"attempts_log={[(a.get('error_class')) for a in al]}")
    return rec, results


for mode in ("fresh", "adopted"):
    rec, results = drive(mode)
    item = results[0] if results else {}
    eclass = item.get("error_class") or rec.get("error_class")
    err = (item.get("error") or rec.get("error") or "")
    check(f"R8 {mode}: the malformed-turn death commits error_class=malformed_turn "
          f"on BOTH runner paths", eclass == "malformed_turn",
          f"error_class={eclass!r} err={err[:160]!r}")
    check(f"R8 {mode}: the verbatim tool-call-as-text diagnostic rides along",
          "tool-call-as-text" in err, f"err={err[:160]!r}")

print("RESULT", "ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
