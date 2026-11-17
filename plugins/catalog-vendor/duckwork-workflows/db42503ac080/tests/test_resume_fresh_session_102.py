#!/usr/bin/env python3
"""#102 bounded re-drive must not pretend-resume a DEAD (empty) session.

Measured 2026-10-01 (issue #102, three lanes burned 4-6h): when the drive-1
child died leaving its session with NO persisted messages (SIGKILL-wave shape),
the re-drive's harvest was pure CLI noise (the death record's raw tail is
startup banner text) and it carried NONE of the node's banked work — drive 2
re-did all discovery from zero and timed out again with zero commits.

Contracts pinned here (runner-side, _bounded_retry):
  EMPTY dead session (sessions row exists, message rows do NOT):
    * the re-drive is decided and logged BEFORE spawn: node.retry carries
      fresh_session=True and the attempts_log entry carries fresh_session;
    * drive-2's prompt_path (the durable prompt as sent) carries a machine
      harvest section seeded from the node's committed/banked work — the
      child work dir's files and their content excerpt — plus the log tail,
      and the dead-session CLI noise ('found but has no messages') is
      stripped so it can never re-ride a later preamble;
    * drive-2 --continues a NEW session title (no dead session id reuse).
  NON-EMPTY dead session (message rows persisted): current behavior —
    standard resume preamble, NO harvest header, no fresh_session key on the
    node.retry event or the attempts_log entry.

Run: cd tests && env -u WF_RUNS_ROOT -u DUCKWORK_HOME HOME=/home/duckwork \
     PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python3 test_resume_fresh_session_102.py
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home102"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(RUNS)   # S3: writers pin the env door
sys.path.insert(0, str(BUILD))

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def mk(run_id, nodes, **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 6}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wf(run_id, extra_env=None, timeout=180):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               FAKE_LOG=str(HOME / "fake.log"), **(extra_env or {}))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def rec_of(r, nid):
    return json.loads((r / "nodes" / f"{nid}.json").read_text())

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
    except FileNotFoundError:
        return []

SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}
MARK = "BANKED-WORKFILE-102"

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")

# ---- A: EMPTY dead session -> fresh-session re-drive seeded with the harvest ----
argv_log = HOME / "argv_empty.log"
r = mk("t102-empty", [{"id": "build", "type": "agent", "goal": "DEADSESS t102-empty",
                       "schema": SCHEMA}])
out = wf("t102-empty", {"FAKE_MODE": "dead_session_102", "FAKE_MESSAGES": "0",
                        "FAKE_ATTEMPT_DIR": str(HOME / "att_empty"),
                        "FAKE_ARGV_LOG": str(argv_log)})
rec = rec_of(r, "build")
check("A recovers to done on the re-drive", rec["status"] == "done"
      and (rec.get("output") or {}).get("result") == "resumed-102", str(rec)[:300])
retry_evts = [e for e in events(r) if e.get("event") == "node.retry"]
check("A exactly ONE bounded re-drive fires", len(retry_evts) == 1, str(retry_evts)[:200])
check("A node.retry DECIDES fresh-session re-drive before spawn (fresh_session=True)",
      retry_evts and retry_evts[0].get("fresh_session") is True, str(retry_evts)[:200])
al = rec.get("attempts_log") or []
check("A attempts_log resume entry carries fresh_session",
      any(a.get("resume") and a.get("fresh_session") for a in al), str(al)[:300])
pp = r / "logs" / "build.a1.prompt.md"
prompt = pp.read_text() if pp.exists() else ""
check("A drive-2 prompt_path carries the machine harvest header",
      "## Dead-session re-drive harvest (machine preamble)" in prompt, prompt[:120])
check("A drive-2 prompt carries the banked/committed work (file name + excerpt)",
      "progress.md" in prompt and MARK in prompt,
      str([p.name for p in (r / "work" / "build").rglob("*") if p.is_file()])
      if (r / "work" / "build").exists() else "no work dir")
check("A drive-2 prompt carries the log tail (drive-1 discovery line)",
      "TAIL-LINE-102" in prompt, prompt[:120])
check("A dead-session noise is stripped from the re-drive prompt (fixture law)",
      "found but has no messages" not in prompt,
      str([l for l in prompt.splitlines() if "found but has no messages" in l][:1]))
lines = argv_log.read_text().splitlines() if argv_log.exists() else []
check("A drive-1 and drive-2 spawned (2 argv lines)", len(lines) == 2, str(lines)[:200])
def cont_title(line):
    parts = line.split()
    return parts[parts.index("--continue") + 1] if "--continue" in parts else ""
t1, t2 = (cont_title(lines[0]), cont_title(lines[1])) if len(lines) == 2 else ("", "")
check("A drive-2 --continues a FRESH session (no dead session id)",
      t1 and t2 and t1 != t2 and t2.startswith(t1.rsplit(".", 1)[0].rsplit("#", 1)[0] + "."),
      f"drive1={t1} drive2={t2}")
check("A run closes done", out.startswith("WORKFLOW_DONE t102-empty"), out[-160:])

# ---- B: NON-EMPTY dead session -> current behavior, byte-identical keys ----
argv_log2 = HOME / "argv_nonempty.log"
r = mk("t102-nonempty", [{"id": "build", "type": "agent", "goal": "DEADSESS t102-nonempty",
                          "schema": SCHEMA}])
out = wf("t102-nonempty", {"FAKE_MODE": "dead_session_102", "FAKE_MESSAGES": "1",
                           "FAKE_ATTEMPT_DIR": str(HOME / "att_nonempty"),
                           "FAKE_ARGV_LOG": str(argv_log2)})
rec = rec_of(r, "build")
check("B recovers to done on the re-drive (non-empty session)", rec["status"] == "done"
      and (rec.get("output") or {}).get("result") == "resumed-102", str(rec)[:300])
retry_evts = [e for e in events(r) if e.get("event") == "node.retry"]
check("B node.retry fires WITHOUT any fresh_session key (behavior unchanged)",
      len(retry_evts) == 1 and "fresh_session" not in retry_evts[0], str(retry_evts)[:200])
al = rec.get("attempts_log") or []
check("B attempts_log entry has NO fresh_session key (unchanged shape)",
      any(a.get("resume") for a in al) and not any("fresh_session" in a for a in al), str(al)[:300])
pp = r / "logs" / "build.a1.prompt.md"
prompt = pp.read_text() if pp.exists() else ""
check("B drive-2 prompt keeps the standard resume preamble",
      "## Resume from a dead attempt (machine preamble)" in prompt
      and "Do not redo finished work; continue from the state above." in prompt, prompt[:120])
check("B drive-2 prompt has NO dead-session harvest header (unchanged)",
      "## Dead-session re-drive harvest (machine preamble)" not in prompt)
lines = argv_log2.read_text().splitlines() if argv_log2.exists() else []
check("B exactly 2 spawns", len(lines) == 2, str(lines)[:200])

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
