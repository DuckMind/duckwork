#!/usr/bin/env python3
"""#116 — confidence_substrate: engine-stamped fallback when a pinned confidence
route is quota-dead.

field case (issue #116 driver): pinned route ping-dead → #25 fail-closes
(correct), but the only lawful recovery was a manual node-by-node recut with
hand-written SUBSTRATE_DISCLOSURE prose — prompt-authored honesty is
theater-adjacent. This test pins the STRUCTURAL law:

  (a) NO config            → fail-closed EXACTLY as today: same error_class /
      message shape, zero substitution fields anywhere (byte-identical law).
  (b) config declares a sanctioned substrate (provider+model) → the door's
      route-decision substitutes the declared rung, stamps nodes/<n>.json via
      the node def (original pin, resolved substrate, reason, config source)
      and re-bakes route_verified to the served substrate.
  (c) the node's result SCHEMA gains the machine-injected disclosure clause
      (bake-time property + required key — a child cannot author it away;
      mirrors the forced answer/schema blocks).
  (d) require_route:false opt-out semantics unchanged (no substitution on an
      opted-out node); an explicit LIVE pin always beats the estate config.
  (e) ladder: config may declare a list; the first rung whose own ping proves
      alive serves; harvest records the rung (served_model law asserted).
  (f) the runner re-validates the engine stamp against the config at commit:
      a stamp whose substrate is NOT the declared config fails closed
      (route_unavailable) — a forged stamp never rides.
  (g) the stamp is policy, not work: def_hash ignores it (A3 law, like
      require_route/route_verified).
  (h) an author-written substrate_substituted is stripped at the door, never
      trusted (route_verified law).
Stdlib only; the core ping seam is stubbed; no network.
"""
import importlib, json, os, subprocess, sys, tempfile, types
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-csub116-", dir=HERE / "tests")
atexit_registered = False
import atexit; atexit.register(tmp_dir.cleanup)
# #71: the shelf is live production — WF_RUNS_ROOT + isolation pin every door write.
os.environ["DUCKWORK_HOME"] = tmp_dir.name
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(Path(tmp_dir.name) / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = "offline"
os.environ.pop("WF_CONFIDENCE_SUBSTRATE", None)

_fake_agent = types.ModuleType("agent"); _fake_agent.__path__ = []
_fake_ru = types.ModuleType("agent.retry_utils")
_fake_ru.parse_retry_after_seconds = lambda x: None
sys.modules["agent"] = _fake_agent
sys.modules["agent.retry_utils"] = _fake_ru

door = importlib.import_module("__init__")
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5
door._CTX = None
door._seat_model_cfg = lambda: {"default": "seat-default", "aliases": {}}
door._seat_aliases = lambda: []
door._seat_default = lambda: "seat-default"
_spawned = []
door._spawn_runner = lambda r: _spawned.append(r.name)

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

class HTTP429(Exception): pass

def set_ping(behavior):
    """Stub the core ping seam like test_require_route_25: behavior keyed by
    (provider, model) — default (raise 429 = DEAD) for the pinned route."""
    def call_llm(task=None, provider=None, model=None, messages=None, max_tokens=None,
                 timeout=None, route_info=None, **kw):
        key = (str(provider or ""), str(model or ""))
        b = behavior.get(key, behavior.get("*", {"raise_": HTTP429("Error code: 429 - rate limited")}))
        if route_info is not None:
            route_info.update(b.get("record", {"provider": str(provider or ""), "model": str(model or "")}))
        exc = b.get("raise_")
        if exc is not None:
            raise exc
        return "pong"
    door._import_call_llm = lambda: call_llm

DEAD = {}                                     # everything 429s
def alive(*routes):                           # named (provider, model) pairs answer
    rec = {"*": {"raise_": HTTP429("Error code: 429 - rate limited")}}
    for p, m in routes:
        rec[(p, m)] = {}
    return rec

def pinned_graph(**extra):
    n = {"id": "a", "type": "agent", "goal": "x", "provider": "openai", "model": "m-1",
         "schema": {"type": "object", "properties": {"result": {"type": "string"}}}}
    n.update(extra)
    return {"name": "p116", "nodes": [n]}

def write_substrate_config(text):
    """Estate config.yaml: top-level `workflows:` section with the owner's
    confidence_substrate key (list or scalar)."""
    (Path(os.environ["DUCKWORK_HOME"]) / "config.yaml").write_text(text)

def clear_substrate_config():
    p = Path(os.environ["DUCKWORK_HOME"]) / "config.yaml"
    if p.exists():
        p.unlink()

def baked(rid):
    return json.loads((Path(os.environ["DUCKWORK_HOME"]) / "workflows" / rid / "graph.json").read_text())

# ---------- (a) NO config: fail-closed byte-identical to #25 as shipped ----------
clear_substrate_config()
set_ping(DEAD)
out = door.act_run({"graph": pinned_graph()})
check("(a1) no config + dead pin: launch refused (route_unavailable at submit)",
      "error" in out and "route_unavailable at submit" in out.get("error", "")
      and "route DEAD at submit" in out.get("error", "") and "'a'" in out["error"], out)
check("(a2) no config: NOTHING spawned", len(_spawned) == 0, _spawned)
check("(a3) no config: no substitution vocabulary anywhere in the refusal",
      "substrate" not in json.dumps(out).lower(), out)
set_ping({"*": {"record": {"provider": "fallback_chain[0](other)", "model": "alt-b"}}})
out = door.act_run({"graph": pinned_graph()})
check("(a4) no config + fallback-ladder surprise: refused, no substitution fields",
      "error" in out and "FALLBACK LADDER" in out.get("error", "")
      and "substrate" not in json.dumps(out).lower(), out)

# ---------- (b) config declares the sanctioned substrate: substitution ----------
SUB_P, SUB_M = "openai", "turbo-a"
write_substrate_config("model:\n  default: seat-default\nworkflows:\n  confidence_substrate:\n"
                       "    - openai/turbo-a\n")
set_ping(alive((SUB_P, SUB_M)))
n_before = len(_spawned)
out = door.act_run({"graph": pinned_graph()})
rid = out.get("run_id")
check("(b1) config + dead pin: LAUNCHES (declared substrate serves)", bool(rid), out)
if rid:
    gj = baked(rid)
    n = gj["nodes"][0]
    check("(b2) node def re-routed to the declared substrate",
          n.get("provider") == SUB_P and n.get("model") == SUB_M, n)
    check("(b3) engine substitution stamp on the node def: from/to/reason/source",
          isinstance(n.get("substrate_substituted"), dict)
          and n["substrate_substituted"].get("from") == "openai/m-1"
          and n["substrate_substituted"].get("to") == f"{SUB_P}/{SUB_M}"
          and n["substrate_substituted"].get("reason")
          and "confidence_substrate" in str(n["substrate_substituted"].get("source", "")),
          n.get("substrate_substituted"))
    check("(b4) route_verified re-baked to the SERVED substrate (no false mismatch)",
          n.get("route_verified") == f"{SUB_P}/{SUB_M}", n)
    # (c) machine-injected disclosure clause in the RESULT SCHEMA
    sch = n.get("schema") or {}
    disc = (sch.get("properties") or {}).get("substrate_disclosure")
    check("(c1) result schema gained substrate_disclosure (engine-injected)",
          isinstance(disc, dict) and disc.get("type") == "string"
          and "m-1" in str(disc.get("description", "")), sch)
    check("(c2) disclosure key is REQUIRED (child cannot author it away)",
          "substrate_disclosure" in (sch.get("required") or []), sch)
    # the runner must accept the baked graph (validator closed set)
    import wfcommon as wc
    check("(c3) baked graph passes the RUNNER validator", not wc.validate_graph(gj["nodes"]),
          str(wc.validate_graph(gj["nodes"])))
    # (e/half) real runner: node DONE + nodes/<n>.json carries the stamp + disclosure
    import shutil
    fake = Path(os.environ["DUCKWORK_HOME"]) / "fake-cs"
    shutil.copy(HERE / "tests" / "fake_duckwork.py", fake); os.chmod(fake, 0o755)
    rdir = Path(os.environ["DUCKWORK_HOME"]) / "workflows" / rid
    (rdir / "run.json").write_text(json.dumps(
        {"duckwork_bin": str(fake), "concurrency": 1, "node_timeout": 60}))
    pr = subprocess.run([sys.executable, str(HERE / "wf.py"), "run", str(rdir)],
                        env=dict(os.environ, DUCKWORK_HOME=os.environ["DUCKWORK_HOME"]),
                        capture_output=True, text=True, timeout=120)
    rec = json.loads((rdir / "nodes" / "a.json").read_text())
    check("(c4) real runner: substituted node commits DONE (engine hold accepts served substrate)",
          rec.get("status") == "done" and "WORKFLOW_DONE" in pr.stdout,
          f"status={rec.get('status')} err={rec.get('error')} out={pr.stdout[:200]}")
    check("(c5) node record carries the engine substitution stamp + disclosure",
          isinstance(rec.get("substrate_substituted"), dict)
          and rec["substrate_substituted"].get("to") == f"{SUB_P}/{SUB_M}"
          and isinstance(rec.get("substrate_disclosure"), str)
          and rec["substrate_disclosure"], rec)
    check("(e1) harvest law: served_model key is recorded on the node record",
          "served_model" in rec, rec)
    # the prompt the child actually got carries the disclosure clause
    prompts = "\n".join(p.read_text() for p in (rdir / "logs").glob("*.prompt.md"))
    check("(c6) the child's prompt carries the schema block with the disclosure clause",
          "substrate_disclosure" in prompts, prompts[:400])
else:
    for lbl in ("(b2)", "(b3)", "(b4)", "(c1)", "(c2)", "(c3)", "(c4)", "(c5)", "(e1)", "(c6)"):
        check(lbl + " (skipped: no launch)", False, "no run_id")

# ---------- (d) opt-outs and precedence ----------
# require_route:false + dead: OLD warn-and-surface launch on the PINNED route —
# substitution is NOT forced onto opted-out nodes (semantics unchanged).
clear_substrate_config(); write_substrate_config(
    "workflows:\n  confidence_substrate:\n    - openai/turbo-a\n")
set_ping(DEAD)
n_before = len(_spawned)
out = door.act_run({"graph": pinned_graph(require_route=False)})
rid = out.get("run_id")
check("(d1) require_route:false + dead + config: launches on the PINNED route, "
      "annotated dead, NO substitution",
      rid and out["routes"]["a"]["liveness"] == "dead" and len(_spawned) == n_before + 1
      and "substrate_substituted" not in baked(rid)["nodes"][0], out)
# explicit LIVE pin always beats the estate config
set_ping(alive(("openai", "m-1")))
out = door.act_run({"graph": pinned_graph()})
rid = out.get("run_id")
check("(d2) live explicit pin + config: launches on the PIN, no substitution",
      rid and "substrate_substituted" not in baked(rid)["nodes"][0]
      and baked(rid)["nodes"][0].get("route_verified") == "openai/m-1", out)
# malformed config = no usable substrate: fail closed exactly as no-config (never
# invent a substitution from garbage)
write_substrate_config("workflows:\n  confidence_substrate: {this is not yaml\n")
set_ping(DEAD)
out = door.act_run({"graph": pinned_graph()})
check("(d3) malformed substrate config: fail-closed as today, no substitution",
      "error" in out and "route_unavailable at submit" in out.get("error", "")
      and "substrate" not in json.dumps(out).lower(), out)
# every rung dead => no alive rung => fail closed with the ORIGINAL message shape
write_substrate_config("workflows:\n  confidence_substrate:\n    - openai/turbo-a\n"
                       "    - deepseek/dx-9\n")
set_ping(DEAD)
out = door.act_run({"graph": pinned_graph()})
check("(d4) ladder fully quota-dead + pin dead: fails closed, original message shape",
      "error" in out and "route DEAD at submit" in out.get("error", "")
      and "substrate" not in json.dumps(out).lower(), out)

# ---------- (e) ladder: first ALIVE rung serves; harvest records the rung ----------
write_substrate_config("workflows:\n  confidence_substrate:\n    - openai/turbo-a\n"
                       "    - openai/pro-c\n")
set_ping(alive(("openai", "pro-c")))     # rung 1 dead, rung 2 alive
out = door.act_run({"graph": pinned_graph()})
rid = out.get("run_id")
check("(e2) ladder: dead rung 1 skipped, alive rung 2 serves",
      rid and baked(rid)["nodes"][0].get("model") == "pro-c"
      and baked(rid)["nodes"][0].get("substrate_substituted", {}).get("to") == "openai/pro-c",
      baked(rid)["nodes"][0] if rid else out)

# ---------- (f) runner: forged/mismatched stamp fails closed ----------
import wf as wfmod
class Meta(dict): pass
meta = Meta({"_run": Path(tmp_dir.name)})
write_substrate_config("workflows:\n  confidence_substrate:\n    - openai/turbo-a\n")
STAMP_OK = {"model": "turbo-a", "provider": "openai",
            "route_verified": "openai/turbo-a",
            "substrate_substituted": {"from": "openai/m-1", "to": "openai/turbo-a",
                                      "reason": "pinned route dead", "source": "config:x[0]"}}
out2 = wfmod._stamp_served(meta, {"status": "done", "output": {"result": "ok"}}, STAMP_OK)
check("(f1) runner: config-declared substituted node commits with stamp + disclosure",
      out2.get("status") == "done"
      and isinstance(out2.get("substrate_substituted"), dict)
      and isinstance(out2.get("substrate_disclosure"), str), out2)
FORGED = dict(STAMP_OK, substrate_substituted=dict(STAMP_OK["substrate_substituted"],
                                                   to="evil/whatever",
                                                   source="config:x[9]"),
              route_verified="evil/whatever", model="whatever", provider="evil")
out3 = wfmod._stamp_served(meta, {"status": "done", "output": {"result": "ok"}}, FORGED)
check("(f2) runner: stamp NOT matching the estate config fails closed (route_unavailable)",
      out3.get("status") == "failed" and out3.get("error_class") == "route_unavailable", out3)
# unknown served_model NEVER fails closed on the substitution path (R2: absence
# is not a mismatch) — (f1) above already exercises skey-less unknown served.
# no-config runner: a stamped node is the door's word (config absence never
# retro-kills a legitimately-substituted node mid-run)
clear_substrate_config()
out4 = wfmod._stamp_served(meta, {"status": "done", "output": {"result": "ok"}}, STAMP_OK)
check("(f3) runner: config removed mid-run — the door's baked stamp rides (no invented death)",
      out4.get("status") == "done", out4)

# ---------- (g) def_hash law: the stamp is policy, not work ----------
import wfcommon as wc2
base = {"id": "a", "type": "agent", "goal": "x", "model": "m-1", "provider": "openai"}
h0 = wc2.def_hash(base)
h1 = wc2.def_hash({**base, "substrate_substituted": {"from": "a", "to": "b"}})
check("(g1) def_hash ignores the substrate_substituted ANNOTATION (A3, like route_verified)",
      h0 == h1, f"{h0} vs {h1}")
check("(g2) def_hash still sees real work changes", wc2.def_hash({**base, "goal": "y"}) != h0)
check("(g3) def_hash still sees a real model change (route key, unlike the proof annotation)",
      wc2.def_hash({**base, "model": "turbo-a"}) != h0)

# ---------- (h) author-forged stamp is stripped at the door ----------
write_substrate_config("workflows:\n  confidence_substrate:\n    - openai/turbo-a\n")
set_ping(alive(("openai", "m-1")))              # pin ALIVE: no substitution should occur
forged = pinned_graph()
forged["nodes"][0]["substrate_substituted"] = {"from": "x", "to": "evil/w", "source": "c",
                                               "reason": "r"}
out_f = door.act_run({"graph": forged})
check("(h1) author-forged substrate_substituted is stripped at resolve, launch proceeds clean",
      out_f.get("run_id") and "substrate_substituted" not in baked(out_f["run_id"])["nodes"][0],
      out_f)
# (h2) F2 idempotence shape: an alive-proved, SUBSTITUTED committed def re-submitted
# VERBATIM must be accepted (the stamp rides like a route key, never trips un-bake).
set_ping(alive(("openai", "turbo-a")))
out_h2 = door.act_run({"graph": {"name": "h2re", "nodes": [
    {"id": "a", "type": "agent", "goal": "x", "model": "turbo-a", "provider": "openai",
     "route_verified": "openai/turbo-a",
     "substrate_substituted": {"from": "openai/m-1", "to": "openai/turbo-a",
                               "reason": "r", "source": "config:x[0]"}}]}})
check("(h2) verbatim committed def WITH stamp still accepted (F2 shape)",
      "error" not in out_h2, out_h2)

# ---------- env override: WF_CONFIDENCE_SUBSTRATE beats/stands in for config ----------
clear_substrate_config()
os.environ["WF_CONFIDENCE_SUBSTRATE"] = "openai/ladder-x,openai/ladder-y"
set_ping(alive(("openai", "ladder-y")))
out = door.act_run({"graph": pinned_graph()})
rid = out.get("run_id")
check("(i1) env-declared ladder substitutes when no config file key exists",
      rid and baked(rid)["nodes"][0].get("model") == "ladder-y", out)
os.environ.pop("WF_CONFIDENCE_SUBSTRATE", None)

print("ALL PASS" if fails == 0 else f"FAILURES: {fails}")
sys.exit(0 if fails == 0 else 1)
