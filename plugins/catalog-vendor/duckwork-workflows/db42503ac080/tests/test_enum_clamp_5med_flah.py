#!/usr/bin/env python3
"""est-flah — unknown enum values clamp at RESOLVE time, never a hard child death.

Verified shapes (field report, 2026-10-02):
  (1) reasoning:high on a narrow-vocabulary relay lane hard-400s ("Supported types are xhigh,
      medium, low") — provider_400 is permfail, the node died with zero recourse;
  (2) `duckwork chat -t none` warns "Unknown toolsets: none" (and the -z path exits 2
      when EVERY name is invalid) instead of no-op.

The runner law pinned here: at spawn, an unknown reasoning-effort clamps to the
nearest supported value (core clamp_effort's weaker-first law) with ONE warning
naming lane / requested / supported set; a toolset list is validated against the
CHILD's own namespace (validate_toolset OR configured mcp_servers OR plugin
toolset keys — deep review #163 B2: bare validate_toolset is NOT the child's
complete view), unknown residue is dropped with one warning, and an all-unknown
list rides VERBATIM — omitting -t would silently broaden the child to the seat's
full default toolsets (boundary probe: 4 declared tools became 41 defaults),
which is never the author's ask. When the
SERVER's own enum-gate 400 names the vocabulary the lane accepts, the runner
re-drives ONCE with the clamped value instead of a permfail (escape hatch), the
server-declared override bypasses the stale local lane table (B1: re-clamping
it re-created the very 400), and the re-drive obeys the #61 quarantine law like
both retry ladders (B3: _isolate_prior before the next Popen, fail closed typed).

CLI-side half (boundary, recorded not patched): the warn+continue lives in core
model_tools._apply_toolset_selection, and the all-invalid -z hard error lives in
duckwork_cli/oneshot.py _validate_explicit_toolsets — this repo clamps on the runner
side so the child never spawns into a known death.

Run: PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_enum_clamp_5med_flah.py
Standalone without core on the path, the toolsets pins assert the documented
pass-through instead (honest degradation — the runner cannot judge what it cannot
import; it never hard-fails).
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home-flah"
RUNS = HOME / "workflows"
sys.path.insert(0, str(BUILD.parent))
import wf, wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " + label + (f"  {detail}" if detail else "")))
    if not cond: ok = False

# Gate on the SAME judgment the runner makes at spawn (wf._filter_child_toolsets
# tries `from toolsets import validate_toolset`), never on a host-layout guess:
# a CI runner can have core importable via site-packages without any /opt tree,
# and asserting the pass-through branch there would pin the opposite of reality.
try:
    import toolsets  # noqa: F401  (the runner's own validator import)
    CORE = True
except Exception:
    CORE = False

# ---------- (a) _nearest_supported: core clamp_effort's law, weaker-first ----------
NS = wf._nearest_supported
check("high on {xhigh,medium,low} -> medium (nearest weaker, never xhigh)",
      NS("high", ["xhigh", "medium", "low"]) == "medium")
check("ultra on {xhigh,medium,low} -> xhigh",
      NS("ultra", ["xhigh", "medium", "low"]) == "xhigh")
check("minimal on {xhigh,medium,low} -> low (supported floor; never escalates up)",
      NS("minimal", ["xhigh", "medium", "low"]) == "low")
check("supported value passes (None = no clamp happened)",
      NS("medium", ["xhigh", "medium", "low"]) is None)
check("bespoke name passes through at resolve (custom providers use them)",
      NS("turbo", ["xhigh", "medium", "low"]) is None)
check("explicit none never clamps (clamping up would switch thinking ON)",
      NS("none", ["xhigh", "medium", "low"]) is None)
check("none excluded as a clamp TARGET (never switches thinking off)",
      NS("high", ["none", "low"]) == "low")
check("empty supported set: no verdict invented",
      NS("high", []) is None and NS("high", None) is None)
check("monotonic: a stronger request never resolves weaker than a weaker one",
      [NS("high", ["low", "medium"]), NS("ultra", ["low", "medium"])]
      == ["medium", "medium"] and NS("medium", ["low", "medium"]) is None)
check("gate-400 marker parses (requested, supported) from the server's own words",
      wf._gate400_parse("duckwork -z: agent failed: Error code: 400 - {{'error': {{'message': "
                        "\"Unsupported type: high. Supported types are xhigh, medium, low\", "
                        "'type': 'invalid_request_error'}}}}") == ("high", ["xhigh", "medium", "low"]),
      str(wf._gate400_parse("Unsupported type: high. Supported types are xhigh, medium, low")))
check("non-enum 400 is NOT a gate (no parse)",
      wf._gate400_parse("Error code: 400 - bad request") is None)

# ---------- harness ----------
FAKE = str(BUILD / "fake-flah"); shutil.copy(BUILD / "fake_duckwork.py", FAKE); os.chmod(FAKE, 0o755)

def mk(run_id, nodes, meta_extra=None):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    meta = {"duckwork_bin": FAKE, "concurrency": 2, "node_timeout": 60}
    meta.update(meta_extra or {})
    (r / "run.json").write_text(json.dumps(meta))
    return r

def drive(run, env_extra):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / f"fake-{run.name}.log"), **env_extra)
    p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", str(run)],
                       env=env, capture_output=True, timeout=180, text=True)
    return p

def events(run):
    return [json.loads(l) for l in (run / "events.jsonl").read_text().splitlines() if l.strip()] \
        if (run / "events.jsonl").exists() else []

def record(run, nid):
    return json.loads((run / "nodes" / f"{nid}.json").read_text())

# ---------- (b) e2e resolve-time clamp: lane table (reasoning_lanes) narrower than declared ----------
if HOME.exists(): shutil.rmtree(HOME)
HOME.mkdir(parents=True); RUNS.mkdir(parents=True)
argv_log = HOME / "argv-lane.log"
r = mk("flah-lane", [{"id": "a", "type": "agent", "goal": "GO lane",
                      "model": "relay-m1", "provider": "relay", "reasoning": "high"}],
       {"reasoning_lanes": {"relay": ["xhigh", "medium", "low"]}})
p = drive(r, {"FAKE_ARGV_LOG": str(argv_log), "FAKE_MODE": ""})
rec = record(r, "a")
argv_lines = argv_log.read_text().splitlines() if argv_log.exists() else []
check("e2e resolve: node DONE (never a permfail death)", rec.get("status") == "done",
      f"{rec.get('status')}/{rec.get('error')}")
check("e2e resolve: ONE spawn — clamp happened before the first Popen, no gate-400 round-trip",
      len(argv_lines) == 1, f"{len(argv_lines)} spawns: {argv_lines}")
check("e2e resolve: --reasoning high became --reasoning medium on the child argv",
      argv_lines and "--reasoning medium" in argv_lines[0]
      and "--reasoning high" not in argv_lines[0], str(argv_lines))
cl = [e for e in events(r) if e.get("event") == "node.clamped"]
check("e2e resolve: exactly ONE warning event", len(cl) == 1, str(cl))
if cl:
    check("warning names kind/requested/clamped", cl[0].get("kind") == "reasoning"
          and cl[0].get("requested") == "high" and cl[0].get("clamped") == "medium", str(cl[0]))
    check("warning names the lane and the supported set",
          "model=relay-m1" in (cl[0].get("lane") or "")
          and "provider=relay" in (cl[0].get("lane") or "")
          and cl[0].get("supported") == ["xhigh", "medium", "low"], str(cl[0]))
    check("warning is human-readable on the runner stdout too",
          "CLAMP" in p.stdout and "high" in p.stdout and "medium" in p.stdout, p.stdout[:200])

# ---------- (c) e2e escape hatch: the SERVER names the vocabulary, one re-drive ----------
argv_log2 = HOME / "argv-gate.log"
r2 = mk("flah-gate", [{"id": "a", "type": "agent", "goal": "GO gate",
                       "model": "relay-m1", "reasoning": "high"}])
p2 = drive(r2, {"FAKE_ARGV_LOG": str(argv_log2), "FAKE_MODE": "reasoning_gate400",
                "FAKE_SUPPORTED_EFFORTS": "xhigh,medium,low", "FAKE_REJECT_EFFORT": "high"})
rec2 = record(r2, "a")
lines2 = argv_log2.read_text().splitlines() if argv_log2.exists() else []
check("e2e gate400: node DONE — the enum-gate 400 was survived, not a permfail",
      rec2.get("status") == "done", f"{rec2.get('status')}/{rec2.get('error')} {rec2.get('error_class')}")
check("e2e gate400: attempt 1 asked high (honest first try), attempt 2 asked medium",
      len(lines2) == 2 and "--reasoning high" in lines2[0] and "--reasoning medium" in lines2[1],
      str(lines2))
check("e2e gate400: exactly ONE re-drive (no loop)", len(lines2) == 2, str(lines2))
cl2 = [e for e in events(r2) if e.get("event") == "node.clamped"]
check("e2e gate400: ONE warning naming requested/clamped/lane/supported",
      len(cl2) == 1 and cl2[0].get("kind") == "reasoning_gate400"
      and cl2[0].get("requested") == "high" and cl2[0].get("clamped") == "medium"
      and cl2[0].get("supported") == ["xhigh", "medium", "low"], str(cl2))
check("e2e gate400: the record carries the clamp evidence",
      rec2.get("reasoning_gate400") == {"requested": "high", "clamped": "medium",
                                        "supported": ["xhigh", "medium", "low"]},
      str(rec2.get("reasoning_gate400")))
check("e2e gate400: attempts_log tells the story (dead gate400 attempt logged)",
      any((e.get("gate400_clamp") == "medium") for e in (rec2.get("attempts_log") or [])),
      str(rec2.get("attempts_log")))
# an ungated 400 must STILL be a permfail — the hatch never widens provider_400
argv_log3 = HOME / "argv-plain400.log"
r3 = mk("flah-plain", [{"id": "a", "type": "agent", "goal": "GO plain", "reasoning": "high"}])
drive(r3, {"FAKE_ARGV_LOG": str(argv_log3), "FAKE_MODE": "provider400"})
rec3 = record(r3, "a")
lines3 = argv_log3.read_text().splitlines() if argv_log3.exists() else []
check("plain provider_400 stays permfail (no enum words: no re-drive)",
      rec3.get("status") == "failed" and rec3.get("error_class") == "provider_400"
      and len(lines3) == 1, f"{rec3.get('error_class')} spawns={len(lines3)}")

# ---------- (c2) deep review #163 B1: the server-declared override bypasses
# the STALE local table. Committee probe verbatim: relay lane table says
# [high], the SERVER says only medium/low exist. Old code re-clamped the
# server's own chosen value back to high — spawn 2 asked high AGAIN, died
# provider_400 twice, while reasoning_gate400 falsely recorded clamped=medium.
# Fixed code passes the server's word through: spawn 2 asks medium and lives.
argv_log7 = HOME / "argv-stale-table.log"
r7 = mk("flah-stale", [{"id": "a", "type": "agent", "goal": "GO stale",
                        "model": "relay-m1", "provider": "relay", "reasoning": "high"}],
       {"reasoning_lanes": {"relay": ["high"]}})   # STALE: contradicts the server
p7 = drive(r7, {"FAKE_ARGV_LOG": str(argv_log7), "FAKE_MODE": "reasoning_gate400",
                "FAKE_SUPPORTED_EFFORTS": "medium,low", "FAKE_REJECT_EFFORT": "high"})
rec7 = record(r7, "a")
lines7 = argv_log7.read_text().splitlines() if argv_log7.exists() else []
check("B1 e2e: server override survives the stale table — node DONE, not provider_400",
      rec7.get("status") == "done",
      f"{rec7.get('status')}/{rec7.get('error_class')} argv={lines7}")
check("B1 e2e: spawn 2 asked the SERVER'S medium, never the table's high again",
      len(lines7) == 2 and "--reasoning medium" in lines7[1]
      and "--reasoning high" not in lines7[1], str(lines7))
check("B1 e2e: the gate400 record tells the truth (requested high -> clamped medium)",
      (rec7.get("reasoning_gate400") or {}).get("clamped") == "medium"
      and (rec7.get("reasoning_gate400") or {}).get("requested") == "high",
      str(rec7.get("reasoning_gate400")))
# unit-level companion: the bypass is the classifier's own law, table present or not
_b = wf._resolve_child_reasoning(r7, {"reasoning_lanes": {"relay": ["high"]}},
                                 {"id": "x", "provider": "relay", "model": "relay-m1",
                                  "reasoning": "high"},
                                 override="medium")
check("B1 unit: server override 'medium' returns verbatim against a table that says ['high']",
      _b == "medium", str(_b))

# ---------- (c3) deep review #163 B3: the gate-400 re-drive obeys the #61
# quarantine law. The dead attempt's backgrounded grandchild (FAKE_GC, same
# group, outlives the child) must be killed + /proc-proven dead BEFORE spawn 2
# — exactly what both retry ladders do via _isolate_prior. Old code re-drove
# blind: the second Popen launched while the first attempt's descendant was
# still alive, sharing the workdir (holdout-head.json B3).
gc_pids = HOME / "gc-b3.pids"
gc_pids.unlink(missing_ok=True)
argv_log8 = HOME / "argv-gate-gc.log"
r8 = mk("flah-gate-gc", [{"id": "a", "type": "agent", "goal": "GO gate gc",
                           "model": "relay-m1", "reasoning": "high"}])
p8 = drive(r8, {"FAKE_ARGV_LOG": str(argv_log8), "FAKE_MODE": "reasoning_gate400",
                "FAKE_SUPPORTED_EFFORTS": "xhigh,medium,low", "FAKE_REJECT_EFFORT": "high",
                "FAKE_GC": "1", "FAKE_GC_PIDS": str(gc_pids)})
rec8 = record(r8, "a")
lines8 = argv_log8.read_text().splitlines() if argv_log8.exists() else []
ev8 = events(r8)
evnames = [e["event"] for e in ev8]
_gcs = [int(x) for x in (gc_pids.read_text().split() if gc_pids.exists() else [])]
_first_gc = _gcs[0] if _gcs else None       # the first attempt's descendant
_reaps = [i for i, e in enumerate(ev8) if e["event"] == "node.respawn_reap"]
_spawns2 = [i for i, e in enumerate(ev8) if e["event"] == "steer.baked"]
check("B3 e2e: gate400 re-drive quarantines BEFORE spawn 2 (respawn_reap between the spawns)",
      len(lines8) == 2 and _reaps and len(_spawns2) >= 2 and _reaps[0] < _spawns2[1],
      f"ev={evnames}")
check("B3 e2e: the quarantine names the FIRST attempt's live descendant",
      _first_gc is not None and any(_first_gc in (e.get("pids") or [])
                                     for i, e in enumerate(ev8)
                                     if e["event"] == "node.respawn_reap" and i < (_spawns2[1] if len(_spawns2) > 1 else 10**9)),
      f"gc={_first_gc} reaps={[e.get('pids') for e in ev8 if e['event']=='node.respawn_reap']}")
_gc_alive = False
for _l in _gcs:
    try:
        os.kill(_l, 0); _gc_alive = True
    except (ProcessLookupError, ValueError):
        pass
    except PermissionError:
        _gc_alive = True
check("B3 e2e: no prior-generation descendant survives to the verdict; node not permfail",
      not _gc_alive and rec8.get("status") in ("done", "partial")
      and (rec8.get("status") == "done" or rec8.get("tree_proof") == "dead"),
      f"status={rec8.get('status')} proof={rec8.get('tree_proof')}")

# ---------- (c4) deep review #163c B3 OPEN: the quarantine FAIL path of the
# gate-400 re-drive. Two defects, one scenario (committee: UnboundLocalError
# proven via dependency-faulted REAL _isolate_prior; attempts_log dropped by
# _left_live_record / _proc_unreadable_record carry-forward tuples):
#   (i) the fail branch reads local `r`, which run_child only binds in the
#       transient ladder (wf.py:3411) — on this path `r` is an unbound local,
#       so the typed fail-closed record dies as NameError instead of committing;
#   (ii) the two quarantine record builders drop attempts_log, so the
#       "quarantine":"failed" stamp on the dead provider_400 attempt is lost —
#       unsatisfiable on the one-line (i) fix alone (adversary finding).
# Fault injection mirrors test_proctree_61b B2: os.listdir("/proc") denied ->
# _isolate_prior must return its typed unreadable record BEFORE spawn 2.
import subprocess as _sp
from unittest.mock import patch as _patch
from wf import _left_live_record as _llr, _proc_unreadable_record as _pur

argv_log9 = HOME / "argv-gate-iso.log"
r9 = mk("flah-gate-iso", [{"id": "a", "type": "agent", "goal": "GO gate iso",
                           "model": "relay-m1", "reasoning": "high"}])
# The fault must exist INSIDE the runner and fire ONLY for /proc reads issued
# from _isolate_prior's own call stack (the committee's dependency-fault method):
# every other /proc channel (admission liveness, run_state) keeps reading truth.
(HOME / "sitecustomize.py").write_text(
    "import os, inspect\n"
    "_real=os.listdir\n"
    "def _u(p):\n"
    "    if str(p)=='/proc':\n"
    "        if any(f.function=='_isolate_prior' for f in inspect.stack()):\n"
    "            raise PermissionError('fault: proc denied in _isolate_prior')\n"
    "    return _real(p)\n"
    "os.listdir=_u\n")
_env9 = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
             FAKE_LOG=str(HOME / "fake-gate-iso.log"),
             FAKE_ARGV_LOG=str(argv_log9), FAKE_MODE="reasoning_gate400",
             FAKE_SUPPORTED_EFFORTS="xhigh,medium,low", FAKE_REJECT_EFFORT="high",
             PYTHONPATH=str(HOME) + os.pathsep + os.environ.get("PYTHONPATH", ""))
p9 = _sp.run([sys.executable, str(BUILD.parent / "wf.py"), "run", str(r9)],
             env=_env9, capture_output=True, timeout=180, text=True)
(HOME / "sitecustomize.py").unlink(missing_ok=True)
rec9 = json.loads((r9 / "nodes" / "a.json").read_text()) \
    if (r9 / "nodes" / "a.json").exists() else {"status": "<no record>"}
lines9 = argv_log9.read_text().splitlines() if argv_log9.exists() else []
check("B3-fail e2e: quarantine-unprovable gate-400 dies TYPED, never a NameError crash",
      rec9.get("error_class") == "left_live_descendants"
      and "UnboundLocalError" not in (rec9.get("error") or "")
      and "NameError" not in (rec9.get("error") or ""),
      f"{rec9.get('status')}/{rec9.get('error_class')}/{(rec9.get('error') or '')[:160]}")
check("B3-fail e2e: NO blind spawn 2 over the unprovable tree (fail closed before Popen)",
      len(lines9) <= 1, f"argv lines: {lines9}")
_al9 = (rec9.get("attempts_log") or [])
check("B3-fail e2e: the typed record CARRIES the dead attempt's log incl. quarantine stamp",
      any(a.get("error_class") == "provider_400" and a.get("quarantine") == "failed"
          for a in _al9),
      json.dumps(_al9)[:300])

# (c4-unit) the two quarantine record builders carry attempts_log forward
_rec_ll = _llr(4242, [4243], "note",
               {"attempts_log": [{"attempt": 0, "error_class": "provider_400"}],
                "raw": "x", "ms": 5})
check("B3-fail unit: _left_live_record carries attempts_log forward",
      _rec_ll.get("attempts_log") == [{"attempt": 0, "error_class": "provider_400"}],
      json.dumps(_rec_ll.get("attempts_log")))
_rec_ur = _pur(4242, "n", 1,
               {"attempts_log": [{"attempt": 0, "error_class": "transport"}]})
check("B3-fail unit: _proc_unreadable_record carries attempts_log forward",
      _rec_ur.get("attempts_log") == [{"attempt": 0, "error_class": "transport"}],
      json.dumps(_rec_ur.get("attempts_log")))

# ---------- (c5) est-vsgj B1-crossed: the server-declared clamp survives the
# OUTER ladders. The (c2) fix sealed only the INNER gate-400 re-drive; a
# transient death after a SUCCESSFUL re-drive (or any outer retry) respawns
# through spawn() with no override and re-learns the very 400 the server already
# answered — argv high-medium-high-medium, one needless gate-400 per respawn
# (est-vsgj's probe verbatim). Law: a server-declared value is a fact for the
# RUN (node, index, lane, author-ask), cached runner-private at the moment the
# server names it; a test-seam override may NEVER write the cache.
argv_log10 = HOME / "argv-outer-ladder.log"
r10 = mk("flah-outer", [{"id": "a", "type": "agent", "goal": "GO outer",
                         "model": "relay-m1", "provider": "relay", "reasoning": "high"}],
        {"reasoning_lanes": {"relay": ["high"]}})   # STALE: contradicts the server
p10 = drive(r10, {"FAKE_ARGV_LOG": str(argv_log10), "FAKE_MODE": "reasoning_gate400",
                  "FAKE_SUPPORTED_EFFORTS": "medium,low", "FAKE_REJECT_EFFORT": "high",
                  "FAKE_GATE_THEN_TRANSPORT": "1", "FAKE_API_CALLS": "0"})
rec10 = record(r10, "a")
lines10 = argv_log10.read_text().splitlines() if argv_log10.exists() else []
_asks10 = [(l.split("--reasoning")[1].split()[0] if "--reasoning" in l else "")
           for l in lines10]
check("B1-crossed e2e: the honest first ask was high, the server answered medium, and the "
      "OUTER ladder respawns kept asking medium (high NEVER re-asks)",
      len(lines10) >= 3 and _asks10[0] == "high"
      and all(a == "medium" for a in _asks10[1:]),
      f"asks={_asks10} status={rec10.get('status')}/{rec10.get('error_class')}")
_cl10 = [e for e in events(r10) if e.get("event") == "node.clamped"
         and e.get("kind") == "reasoning_gate400"]
check("B1-crossed e2e: the gate-400 lesson was learned ONCE — exactly one clamp event total",
      len(_cl10) == 1, f"{len(_cl10)} clamp events: {_cl10}")
# unit: the cache is the resolve classifier's own law
_cache = {}
_u_meta = {"reasoning_lanes": {"relay": ["high"]}}
_u_node = {"id": "u", "provider": "relay", "model": "relay-m1", "reasoning": "high"}
_v1 = wf._resolve_child_reasoning(r10, _u_meta, _u_node, override="medium",
                                  override_source="server", index=None, cache=_cache)
check("B1-crossed unit: a server-sourced override returns verbatim AND seeds the cache",
      _v1 == "medium" and list(_cache.values()) == ["medium"],
      f"{_v1} cache={_cache}")
_v2 = wf._resolve_child_reasoning(r10, _u_meta, _u_node, index=None, cache=_cache)
check("B1-crossed unit: the outer-ladder re-ask (author's high vs stale table [high]) "
      "resolves from the cache — medium, never the server-rejected high",
      _v2 == "medium", str(_v2))
_v3 = wf._resolve_child_reasoning(r10, _u_meta, _u_node, override="low",
                                  override_source=None, index=None, cache=_cache)
check("B1-crossed unit: a TEST-SEAM override passes through but can never poison the cache",
      _v3 == "low" and list(_cache.values()) == ["medium"], f"{_v3} cache={_cache}")
# isolation: different index / different author-ask never shares a slot
_c2x = {}
wf._resolve_child_reasoning(r10, _u_meta, _u_node, override="medium",
                            override_source="server", index=None, cache=_c2x)
_wf_fresh = wf._resolve_child_reasoning(r10, _u_meta, _u_node, override="low",
                                        override_source="server", index=3, cache=_c2x)
_v4 = wf._resolve_child_reasoning(r10, _u_meta, _u_node, index=3, cache=_c2x)
_v5 = wf._resolve_child_reasoning(
    r10, _u_meta, {"id": "u", "provider": "relay", "model": "relay-m1", "reasoning": "ultra"},
    index=None, cache=_c2x)
check("B1-crossed unit: cache slots are per (node,index,lane,author-ask) — fanout items "
      "and different asks never inherit each other's value",
      _wf_fresh == "low" and _v4 == "low" and len(_c2x) == 2 and _v5 != "medium",
      f"idx3={_v4} ultra={_v5} cache={_c2x}")

# ---------- (d) e2e toolsets: unknown names are a clean no-op, never a child death ----------
def toolsets_run(run_id, toolsets_value, argv_log_path):
    r = mk(run_id, [{"id": "a", "type": "agent", "goal": f"GO {run_id}", "toolsets": toolsets_value}])
    p = drive(r, {"FAKE_ARGV_LOG": str(argv_log_path), "FAKE_MODE": "toolset_warn_ok"})
    return r, p, record(r, "a"), (argv_log_path.read_text().splitlines() if argv_log_path.exists() else [])

if CORE:
    r4, p4, rec4, lines4 = toolsets_run("flah-ts-none", ["none"], HOME / "argv-ts-none.log")
    check("e2e toolsets: -t none is a CLEAN no-op (flag omitted), child DONE",
          rec4.get("status") == "done" and lines4 and " -t " not in (" " + lines4[0] + " ")
          and not lines4[0].endswith("-t"), f"{rec4.get('status')} argv={lines4}")
    cl4 = [e for e in events(r4) if e.get("event") == "node.clamped"]
    check("e2e toolsets: ONE warning naming requested 'none'",
          len(cl4) == 1 and cl4[0].get("kind") == "toolsets"
          and cl4[0].get("requested") == "none", str(cl4))

    r5, _, rec5, lines5 = toolsets_run("flah-ts-mixed", ["web", "bogus"], HOME / "argv-ts-mixed.log")
    check("e2e toolsets: mixed list keeps the valid name, drops the bogus one",
          rec5.get("status") == "done" and lines5 and "-t web" in lines5[0]
          and "bogus" not in lines5[0], f"{rec5.get('status')} argv={lines5}")
    cl5 = [e for e in events(r5) if e.get("event") == "node.clamped"]
    check("e2e toolsets: ONE warning names requested 'web,bogus' -> kept 'web'",
          len(cl5) == 1 and cl5[0].get("requested") == "web,bogus"
          and cl5[0].get("clamped") == "web", str(cl5))

    # an unknown reasoning value against an unknown lane table still rides the
    # gate400 hatch (no table invented): fake rejects what core's widest table
    # DOES contain but a narrow relay would not (FAKE_REJECT_EFFORT drives it).
    r6, _, rec6, lines6 = toolsets_run("flah-ts-none-ok", ["web"], HOME / "argv-ts-ok.log")
    check("e2e toolsets: all-valid list passes through byte-identical (-t web)",
          rec6.get("status") == "done" and lines6 and "-t web" in lines6[0], str(lines6))
    check("e2e toolsets: all-valid list logs NO clamp",
          not [e for e in events(r6) if e.get("event") == "node.clamped"], "")

    # ---------- (d2) deep review #163 B2: the child's namespace, not the bare
    # validator. Configured-but-unregistered MCP names are KEPT (the child's own
    # _init_toolsets would keep them; the runner dropping them + omitting -t
    # silently broadened a 4-tool graph to 41 defaults); an all-unknown list
    # rides VERBATIM — the flag is NEVER silently omitted.
    r_ts = mk("flah-ts-unit", [{"id": "x", "type": "agent", "goal": "GO ts", "toolsets": ["bogus-xyz"]}])
    out_ts = wf._filter_child_toolsets(r_ts, {}, {"id": "x", "toolsets": ["bogus-xyz"]})
    check("B2 unit: all-unknown list rides VERBATIM (never None: omission = silent broadening)",
          out_ts == ["bogus-xyz"], str(out_ts))
    (HOME / "config.yaml").write_text(
        "mcp_servers:\n  audit_mcp:\n    command: /bin/true\n    enabled: true\n")
    # read_raw_config resolves config.yaml from DUCKWORK_HOME at CALL time — the
    # in-process unit needs the env pointed at the fixture home (restore after).
    _saved_home = os.environ.get("DUCKWORK_HOME")
    os.environ["DUCKWORK_HOME"] = str(HOME)
    os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
    try:
        out_mcp = wf._filter_child_toolsets(r_ts, {}, {"id": "x",
                                                       "toolsets": ["bogus-xyz", "audit_mcp"]})
    finally:
        if _saved_home is None: os.environ.pop("DUCKWORK_HOME", None)
        else: os.environ["DUCKWORK_HOME"] = _saved_home
    check("B2 unit: configured mcp_servers name survives the runner filter (child's own namespace)",
          out_mcp == ["audit_mcp"], str(out_mcp))
    (HOME / "config.yaml").unlink(missing_ok=True)
    out_mix = wf._filter_child_toolsets(r_ts, {}, {"id": "x",
                                                    "toolsets": ["web", "bogus-xyz"]})
    check("B2 unit: mixed list keeps valid, drops only the true unknown",
          out_mix == ["web"], str(out_mix))
    out_none = wf._filter_child_toolsets(r_ts, {}, {"id": "x", "toolsets": ["none"]})
    check("B2 unit: the author's explicit 'none' sentinel still means omission",
          out_none is None, str(out_none))
else:
    # honest degradation documented: without the core validator importable the
    # runner passes names through (warn+continue is core's job on the chat path)
    # and never hard-fails the spawn.
    r4, _, rec4, lines4 = toolsets_run("flah-ts-none", ["none"], HOME / "argv-ts-none.log")
    check("no-core: unknown toolset passes through and the child still runs",
          rec4.get("status") == "done" and lines4 and "-t none" in lines4[0],
          f"{rec4.get('status')} argv={lines4}")

print("DONE enum_clamp_5med_flah", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
