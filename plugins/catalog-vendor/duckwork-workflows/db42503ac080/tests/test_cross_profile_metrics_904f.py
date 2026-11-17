#!/usr/bin/env python3
"""Regression pin fb 904f5101496be8c1: status/wait showed zero api/tool/tokens and
idle_s=null for profile-routed fanout children, because the door's cumulative-metrics
fold (act_status) read ONLY the caller's state.db. The children live in the TARGET
profile's state.db (proven live case: run 20260930-145454-wofs-w1c-coldread-5a160d,
4 zap-routed readers with 13/22/12/17 api calls, door showed zero).

S1  the fold seam run_child_metrics finds rows that live in a routed node's OWN
    profile home (pre-fix: child_metrics(run_id) alone returns {}).
S2  solo byte-identity: a run whose node records carry no profile keys folds exactly
    child_metrics(default_home) — same dict, no extra DB reads.
S3  static audit: the door's status path must go through the profile-aware fold —
    no bare child_metrics(st["run_id"]) call left in __init__.py.

Standalone script (NOT pytest):
  PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_cross_profile_metrics_904f.py
"""
import os
import sqlite3
import sys
import tempfile
import types
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
# #71 law: pin the runs root beside every home sandbox — the shelf is live production.
os.environ["DUCKWORK_HOME"] = str(Path(_tmp.name) / "home")
os.environ["WF_RUNS_ROOT"] = str(Path(_tmp.name) / "home" / "workflows")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wfcommon as C  # noqa: E402

RUN = "20260930000000-fake-profile-metrics"
SESSION_COLS = ("title TEXT, model TEXT, billing_provider TEXT, input_tokens INTEGER, "
                "output_tokens INTEGER, cache_read_tokens INTEGER, reasoning_tokens INTEGER, "
                "api_call_count INTEGER, tool_call_count INTEGER, estimated_cost_usd REAL, "
                "last_activity_at TEXT, last_activity_description TEXT, ended_at TEXT, "
                "started_at TEXT")


def seed_db(home: Path, rows):
    """Create a state.db with one sessions row per (title, api, tools)."""
    home.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(home / "state.db")
    c.execute(f"CREATE TABLE sessions ({SESSION_COLS})")
    for title, api, tools in rows:
        c.execute("INSERT INTO sessions (title, model, api_call_count, tool_call_count, "
                  "input_tokens, output_tokens, last_activity_at, started_at) "
                  "VALUES (?, 'test-model', ?, ?, 100, 50, '2026-09-30T15:00:00', '2026-09-30T14:00:00')",
                  (title, api, tools))
    c.commit()
    c.close()


def make_run(run_home: Path, node_records: dict):
    """Minimal run dir: graph.json + nodes/*.json records as given."""
    (run_home / "nodes").mkdir(parents=True, exist_ok=True)
    import json
    (run_home / "graph.json").write_text(json.dumps(
        {"name": "fake", "nodes": [{"id": "readers", "type": "agent", "goal": "g"}]}))
    for name, rec in node_records.items():
        (run_home / "nodes" / f"{name}.json").write_text(json.dumps(rec))


CHECKS = []


def check(label, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + label + ((("  -- " + str(detail)[:140]) if detail else "") if not cond else ""))
    CHECKS.append(label)
    if not cond:
        globals()["FAILS"].append(label)


FAILS = []

# ---- S1: routed node's rows are found through its OWN profile home ----
with tempfile.TemporaryDirectory() as t1:
    base = Path(t1)
    launcher_home = base / "launcher"
    launcher_home.mkdir()
    seed_db(launcher_home, [])                     # launcher DB exists but holds NOTHING
    zap_home = base / "profiles" / "zap"
    seed_db(zap_home, [(f"wf:{RUN}:readers:0:abcd.1111#a0", 13, 27),
                       (f"wf:{RUN}:readers:1:abcd.2222#a0", 22, 35)])
    run_home = launcher_home / "workflows" / RUN
    make_run(run_home, {
        "readers.0": {"status": "done", "profile": "zap", "profile_home": str(zap_home)},
        "readers.1": {"status": "done", "profile": "zap", "profile_home": str(zap_home)},
    })
    # Pre-fix behavior, pinned honestly: the naive fold over the launcher DB sees nothing.
    import wfcommon
    old_home = wfcommon.duckwork_home
    wfcommon.duckwork_home = lambda: launcher_home   # caller seat = launcher
    try:
        naive = C.child_metrics(RUN)
        check("S1a naive default-home fold is empty (the bug's shape)", naive == {}, naive)
        cm = C.run_child_metrics(run_home)
        total_api = sum(m.get("api_calls", 0) for m in cm.values())
        check("S1b profile-aware fold finds the routed rows", total_api == 35, cm)
        check("S1c both item skeys present", len(cm) == 2, list(cm))
        check("S1d counters are the routed DB's", 
              sorted(m["tool_calls"] for m in cm.values()) == [27, 35], cm)
    finally:
        wfcommon.duckwork_home = old_home

# ---- S2: solo byte-identity — no profile records => exactly the default fold ----
with tempfile.TemporaryDirectory() as t2:
    base = Path(t2)
    solo_home = base / "solo"
    seed_db(solo_home, [(f"wf:{RUN}:build:abcd.9999#a0", 7, 11)])
    run_home = solo_home / "workflows" / RUN
    make_run(run_home, {"build": {"status": "done"}})   # no profile keys at all
    old_home = C.duckwork_home
    C.duckwork_home = lambda: solo_home
    try:
        want = C.child_metrics(RUN)
        got = C.run_child_metrics(run_home)
        check("S2 solo fold is byte-identical to child_metrics", got == want and want != {},
              {"want": bool(want), "got": bool(got)})
    finally:
        C.duckwork_home = old_home

# ---- S3: the door's status path uses the seam, no bare fold left ----
src = Path(__file__).resolve().parent.parent / "__init__.py"
text = src.read_text()
check("S3 no bare child_metrics(st[\"run_id\"]) in the door",
      'child_metrics(st["run_id"])' not in text and "run_child_metrics" in text)

# ---- S4 (est-la8m): the DASHBOARD's full view uses the same seam ----
# The door fixed its fold in PR #79 (bc44977); dashboard/plugin_api.py _view(full)
# kept the bare caller-home fold, so the WORKFLOWS full view false-zeroed every
# profile-routed child (issue #81) even while the door's status read them fine.
dash = Path(__file__).resolve().parent.parent / "dashboard" / "plugin_api.py"
dtext = dash.read_text()
check("S4 no bare child_metrics(st[\"run_id\"]) in the dashboard full view",
      'child_metrics(st["run_id"])' not in dtext and "run_child_metrics(r)" in dtext)

print("TOTAL", len(CHECKS), "FAIL", len(FAILS))
sys.exit(1 if FAILS else 0)
