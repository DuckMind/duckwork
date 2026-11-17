#!/usr/bin/env python3
"""Regression pin: the wake suites are hermetic against an INHERITED
WF_RUNS_ROOT / API_SERVER_* environment, not just a clean CI environment.

Failure mode pinned: the runs-root resolver precedence (#42) is

    settings.runs_root  >  WF_RUNS_ROOT env  >  <duckwork_home>/workflows

so DUCKWORK_HOME alone is NOT a sandbox. tests/test_session_wake_101.py used to
build its child env as `dict(os.environ, DUCKWORK_HOME=tmp, ...)` — a
WF_RUNS_ROOT or API_SERVER_* variable inherited from the invoking process
OUTRANKS the test's home, every spawned runner resolves elsewhere, and the
suite dies "WORKFLOW_FAILED w1 (no graph.json)" ~30 checks deep while the
identical tree passes on a clean CI runner (reproduce:
`env WF_RUNS_ROOT=/tmp/hostile API_SERVER_KEY=SYNTH python tests/test_session_wake_101.py`
-> RC=1, TOTAL 42 FAIL 30; RC=0 TOTAL 42 FAIL 0 clean). The sibling wake
suites already strip + self-pin (matrix_101 base_env, lost_handoff ENV); this
file is the tripwire that the same practice holds for the whole wake family
and that nobody deletes the pin again.

Two legs, both directions:
  (A) POSITIVE CONTROL (the bug): a copy of the pre-fix env() shape — dict-merge
      over os.environ, DUCKWORK_HOME only — run under a stray WF_RUNS_ROOT must
      reproduce the failure: the child writes NOTHING to the test's own
      tmp/workflows and its stdout degrades to "no graph.json". If this leg
      ever FAILS (the child unexpectedly succeeded), the resolver precedence
      changed under our feet and this whole section must be re-derived, exactly
      like the S4a counter-probe in test_shelf_isolation_71.py.
  (B) THE PIN: the fixed env() shape (strip WF_RUNS_ROOT/API_SERVER_*, set our
      own WF_RUNS_ROOT) run under the SAME stray root must produce the real
      transition: WORKFLOW_HELD on stdout and exactly one gate.held row in
      <run>/wake.jsonl, delivered to the test's own sink.

  (C) STATIC audit: every tests/*.py that spawns `wf.py run` as a child AND
      reads wake.jsonl must carry its own WF_RUNS_ROOT pin in source — the
      wake family this suite names. (Scoped deliberately: other legacy suites
      spawn runners via DUCKWORK_HOME alone and are outside this suite's scope.)

Red discipline: with the pin removed from test_session_wake_101.py, leg (A)
still passes (the control is a local copy) BUT leg (C) names the file and the
suite exits 1 — the bug reproduces as a hard failure of THIS test.
usage: python3 test_wake_hermetic_env.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

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

FAKE = str(HERE / "fake")
OWNER = {"session_id": "hermetic-session", "ui_session_id": "hermetic-ui", "platform": "api_server"}
G_HOLD = [{"id": "n1", "type": "agent", "goal": "LIST: go"},
          {"id": "g1", "type": "gate", "after": ["n1"], "question": "ship?",
           "options": ["yes", "no"]}]

# ---- local sink (the delivery stub) ----
sinks = []

class _Sink(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(n)
        sinks.append(json.loads(body.decode() or "{}"))
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"{}")
    def log_message(self, *a):
        pass

_srv = ThreadingHTTPServer(("127.0.0.1", 0), _Sink)
threading.Thread(target=_srv.serve_forever, daemon=True).start()
SINK_PORT = _srv.server_address[1]

tmp = Path(tempfile.mkdtemp(prefix="wf-hermetic-"))
(tmp / "fake.log").write_text("")
RUNS = tmp / "workflows"
STRAY = tmp / "stray-hostile-runs"         # what an inherited WF_RUNS_ROOT would pin
STRAY.mkdir()

# a run pre-made in the TEST's own root (what mk() does in the real suite)
def mk(run_id):
    r = RUNS / run_id
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": G_HOLD}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": FAKE, "concurrency": 1, "node_timeout": 60, "owner": OWNER}))
    return r

def wake_rows(r):
    p = r / "wake.jsonl"
    try:
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []

def drive(r, e):
    return subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", r.name],
                          env=e, capture_output=True, text=True, timeout=90, cwd=str(ROOT))

try:
    # ---- (A) POSITIVE CONTROL: the PRE-FIX env shape leaks under a stray pin ----
    # Byte-for-byte the old construction: merge over os.environ, scope by DUCKWORK_HOME.
    ra = mk("hermetic-a")
    e_bad = dict(os.environ, DUCKWORK_HOME=str(tmp), WF_WAKE_SINK_PORT=str(SINK_PORT),
                 FAKE_LOG=str(tmp / "fake.log"), WF_RUNS_ROOT=str(STRAY))
    outa = drive(ra, e_bad)
    check("A-control: pre-fix shape leaks — stray WF_RUNS_ROOT hijacks the child",
          "no graph.json" in outa.stdout and not wake_rows(ra)
          and not (STRAY / ra.name).exists(),
          f"stdout={outa.stdout[:120]!r} wakes={wake_rows(ra)} stray_dir={(STRAY / ra.name).exists()}")

    # ---- (B) THE PIN: the FIXED env shape is immune to the SAME stray env ----
    # The stray WF_RUNS_ROOT + API_SERVER_* ride os.environ (the real
    # inheritance shape); the fixed env() construction strips them and sets its
    # own root — byte-for-byte the pinned shape now in test_session_wake_101.py.
    rb = mk("hermetic-b")
    saved = {k: os.environ.get(k) for k in ("WF_RUNS_ROOT", "API_SERVER_KEY",
                                            "API_SERVER_HOST", "API_SERVER_PORT")}
    os.environ["WF_RUNS_ROOT"] = str(STRAY)
    os.environ["API_SERVER_KEY"] = "SYNTH-TEST-KEY"
    try:
        e_good = dict(os.environ)
        for k in ("WF_RUNS_ROOT", "API_SERVER_KEY", "API_SERVER_HOST", "API_SERVER_PORT"):
            e_good.pop(k, None)
        e_good.update(DUCKWORK_HOME=str(tmp), WF_RUNS_ROOT=str(RUNS),
                      WF_WAKE_SINK_PORT=str(SINK_PORT), FAKE_LOG=str(tmp / "fake.log"))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    outb = drive(rb, e_good)
    wb = wake_rows(rb)
    check("B-pin: held transition lands in the test's OWN root despite a stray env",
          outb.stdout.startswith(f"WORKFLOW_HELD {rb.name} g1"), outb.stdout[:160])
    check("B-pin: exactly one gate.held wake row, delivered, names the run",
          len(wb) == 1 and wb[0].get("event") == "gate.held"
          and wb[0].get("delivered") is True and rb.name in wb[0].get("text", ""),
          f"wakes={wb} posts={len(sinks)}")
    check("B-pin: the stray hostile root gained no run dirs",
          not (STRAY / rb.name).exists(), str(sorted(p.name for p in STRAY.iterdir())))

    # ---- (C) STATIC audit: wake-family runner spawners pin their own root ----
    import re
    spawn_re = re.compile(r"wf\.py[\"']\)[^\]]*?\"run\"")
    leakers = []
    for p in sorted(HERE.glob("*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if spawn_re.search(t) and "wake.jsonl" in t and "WF_RUNS_ROOT" not in t:
            leakers.append(p.name)
    check("C-audit: every wake-suite wf.py-run spawner pins WF_RUNS_ROOT",
          not leakers, f"leakers: {leakers}")
finally:
    _srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

print(f"TOTAL {checks} FAIL {failures}")
sys.exit(1 if failures else 0)
