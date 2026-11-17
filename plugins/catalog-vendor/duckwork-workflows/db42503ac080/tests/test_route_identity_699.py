#!/usr/bin/env python3
"""est-2ek.1.699 — route IDENTITY: dotted vs hyphenated model aliases.

Field evidence run 20261005-030530-zap-banked-findings-squa: nodes pinned a
dotted Anthropic id (5.1); the door's submit ping PROVED it alive on anthropic
(route_verified baked, liveness alive) and the items completed — yet the commit
hold marked them route_unavailable because core normalizes/bills the model id
with a hyphen (5-1). The door's proof and the runner's identity law compared RAW
strings, so the same route under two spellings billed as a different one.

The fix is ONE provider normalization contract (wfcommon.canonical_model_id)
used by BOTH the submit-proof comparison (door ping same-route law) and the
actual-child identity comparisons (runner commit hold + post-admission receipt
hold). Acceptance pinned here:
  * dot/hyphen equivalence is Anthropic-only; other providers and aggregator vendor
    namespaces compare as spelled (section 4, from the review on PR #238)
  * alias pair 5.1 vs 5-1 -> proven-and-run items are NOT route_unavailable
  * a genuinely different model stays blocked (require_route NOT weakened —
    no fallback enabled, the gate itself unchanged)
  * a dead pin is still refused at submit; legacy runs (no route_verified) are
    byte-identical.
Stdlib only; the seat stub is a recording fake; no network.
"""
import importlib, json, os, sys, tempfile, types
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-routeid699-", dir=HERE / "tests")
import atexit
atexit.register(tmp_dir.cleanup)
os.environ["DUCKWORK_HOME"] = tmp_dir.name
os.environ["WF_RUNS_ROOT"] = str(Path(tmp_dir.name) / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = "offline"

_fake_agent = types.ModuleType("agent"); _fake_agent.__path__ = []
_fake_ru = types.ModuleType("agent.retry_utils")
_fake_ru.parse_retry_after_seconds = lambda x: None
sys.modules["agent"] = _fake_agent
sys.modules["agent.retry_utils"] = _fake_ru

import wfcommon as wc
import wf as wfmod

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

# Fixtures (neutral names; the claude- prefix is load-bearing: stock core folds
# '.'->'-' ONLY for claude prefixed Anthropic ids). Every scrub hit in this file
# lives in this block, and only these lines are allow-listed in .scrub-guards.
DOT, HY = "claude-model-5.1", "claude-model-5-1"
OTHER = "claude-other-8"
UNDER = "claude-model-5_1"
BEDROCK_DOT, BEDROCK_HY = "us.anthropic.claude-model-5-1", "us-anthropic-claude-model-5-1"
FALLBACK = "seat-fallback-9"
SUF_OFF, SUF_ON = "model-1", "model-1(extra)"
OAI_PRE = "openai-codex"

# ---- 0. the ONE canonical normalizer exists and is the shared contract ---------
check("canonical_model_id exported by wfcommon (the shared contract)",
      callable(getattr(wc, "canonical_model_id", None)))
if callable(getattr(wc, "canonical_model_id", None)):
    cm = lambda m, prov="anthropic": wc.canonical_model_id(m, prov)   # the pin's provider
    check("alias pair 5.1 vs 5-1 canonicalize EQUAL",
          cm(DOT) == cm(HY), f"{cm(DOT)!r} vs {cm(HY)!r}")
    check("provider-qualified strips to the same model identity",
          cm("anthropic/" + DOT) == cm(HY) == cm("anthropic/" + HY),
          f"{cm('anthropic/' + DOT)!r} vs {cm(HY)!r}")
    check("different models stay DIFFERENT (no fuzzy equality)",
          cm(OTHER) != cm(DOT) and cm(FALLBACK) != cm(DOT))
    # review of #296 (P1, required repair): stock core PRESERVES a literal
    # '(suffix)' and records the concrete model verbatim — the contract must NOT
    # peel it for any provider. Refusal in both directions, any provider.
    check("literal suffix preserved (unit): model-1(extra) != model-1 [openai-codex]",
          wc.canonical_model_id(SUF_ON, OAI_PRE) != wc.canonical_model_id(SUF_OFF, OAI_PRE),
          wc.canonical_model_id(SUF_ON, OAI_PRE))
    check("literal suffix preserved (unit): model-1 != model-1(extra) [openai-codex]",
          wc.canonical_model_id(SUF_OFF, OAI_PRE) != wc.canonical_model_id(SUF_ON, OAI_PRE))
    check("literal suffix preserved (unit): claude dotted+sfx != hyphen-bare [anthropic]",
          not wc.route_ids_equal(DOT + "(extra)", HY, "anthropic"),
          wc.canonical_model_id(DOT + "(extra)", "anthropic"))
    check("case/whitespace insensitive",
          cm("  Anthropic/" + DOT.upper() + " ") == cm(HY))
    # provider boundary: the dot/hyphen equivalence is Anthropic's alone, and a vendor
    # namespace on an aggregator route is part of the id (zap review on PR #238)
    check("openai-codex keeps dots: model-5.1 != model-5-1",
          wc.canonical_model_id("model-5.1", "openai-codex") != wc.canonical_model_id("model-5-1", "openai-codex"))
    check("openrouter keeps the vendor namespace: vendor-a/alpha != vendor-b/alpha",
          wc.canonical_model_id("vendor-a/alpha", "openrouter") != wc.canonical_model_id("vendor-b/alpha", "openrouter"))
    check("only the route's OWN provider prefix is peeled",
          wc.canonical_model_id("openrouter/vendor-a/alpha", "openrouter") == wc.canonical_model_id("vendor-a/alpha", "openrouter")
          and wc.canonical_model_id("vendor-a/alpha", "openrouter") == "vendor-a/alpha")
    check("provider-less ids compare as spelled", wc.canonical_model_id("m-5.1") != wc.canonical_model_id("m-5-1"))
    check("hyphen runs are left alone", wc.canonical_model_id("m--1", "anthropic") == "m--1")
    # review of #296 (P1a): mirror stock core normalize_model_name exactly — '.'->'-'
    # per dot, claude prefixed ids only, '_' preserved, Bedrock namespace dots kept
    check("non-claude anthropic id keeps dots: m..1 != m-1",
          not wc.route_ids_equal("m..1", "m-1", "anthropic"), wc.canonical_model_id("m..1", "anthropic"))
    check("non-claude id keeps dots on anthropic: model-5.4 != model-5-4",
          not wc.route_ids_equal("model-5.4", "model-5-4", "anthropic"))
    check("underscore is preserved: 5_1 != 5-1",
          not wc.route_ids_equal(UNDER, HY, "anthropic"), wc.canonical_model_id(UNDER, "anthropic"))
    check("Bedrock namespace dots survive",
          not wc.route_ids_equal(BEDROCK_DOT, BEDROCK_HY, "anthropic"), wc.canonical_model_id(BEDROCK_DOT, "anthropic"))
    check("each dot folds singly (stock replace): claude x..1 -> x--1",
          wc.canonical_model_id(DOT.replace(".", ".."), "anthropic") == HY.replace("5-1", "5--1"))

# ---- 1. runner commit hold: dotted proof vs hyphenated billed -> NO hold --------
# Exact field shape: door proved anthropic/<dotted>, the row billed the
# hyphenated spelling for a node that completed.
meta = {"_run": Path(tmp_dir.name)}
PROOF = {"model": DOT, "provider": "anthropic", "route_verified": f"anthropic/{DOT}"}
out = wfmod._route_hold(meta, {"status": "done", "served_model": HY}, PROOF)
check("commit hold: proven-and-run alias pair (5.1 proved, 5-1 billed) -> NOT route_unavailable",
      out.get("status") == "done", out)
# reverse spelling: proved hyphenated, billed dotted
out = wfmod._route_hold(meta, {"status": "done", "served_model": DOT},
                        {"model": HY, "provider": "anthropic",
                         "route_verified": f"anthropic/{HY}"})
check("commit hold: reverse spelling (5-1 proved, 5.1 billed) -> NOT route_unavailable",
      out.get("status") == "done", out)
# provider-qualified served row
out = wfmod._route_hold(meta, {"status": "done", "served_model": f"anthropic/{HY}"}, PROOF)
check("commit hold: provider-qualified billed alias passes", out.get("status") == "done", out)
# require_route NOT weakened: a genuinely different billed model still fails
out = wfmod._route_hold(meta, {"status": "done", "served_model": OTHER}, PROOF)
check("commit hold: different model billed despite alive proof -> still route_unavailable",
      out.get("status") == "failed" and out.get("error_class") == "route_unavailable", out)
out = wfmod._route_hold(meta, {"status": "done", "served_model": FALLBACK}, PROOF)
check("commit hold: seat fallback still route_unavailable", out.get("status") == "failed", out)
# unknown served / no proof: legacy laws byte-identical
check("commit hold: unknown served passes (never invents known)",
      wfmod._route_hold(meta, {"status": "done", "served_model": None}, PROOF)["status"] == "done")
check("commit hold: no route_verified -> no hold (legacy identity)",
      wfmod._route_hold(meta, {"status": "done", "served_model": "whatever"},
                        {"model": DOT})["status"] == "done")
# seat alias map still honored under the normalizer
seat = Path(tmp_dir.name) / "seat699"; seat.mkdir(exist_ok=True)
(seat / "config.yaml").write_text(f"model:\n  aliases:\n    {HY.replace('.', '-')}: anthropic/{DOT}\n")
class FRResult(dict):
    def get(self, k, d=None):
        return str(seat) if k == "profile_home" else dict.get(self, k, d)
out = wfmod._route_hold(meta, FRResult({"status": "done", "served_model": HY}),
                        {"model": HY, "route_verified": f"anthropic/{HY}"})
check("commit hold: seat alias spelling passes", out.get("status") == "done", out)

# ---- 2. post-admission receipt hold: same ONE contract --------------------------
# The lane has a proved-alive receipt for dotted; a re-spawn that asks the hyphenated
# spelling of the SAME route must NOT be a substitution (no self-certification
# widening: a different model stays denied).
node_dot = {"id": "plans", "type": "agent", "goal": "g",
            "provider": "anthropic", "model": DOT, "route_verified": f"anthropic/{DOT}"}
lane699 = Path(tmp_dir.name) / "lane699"; (lane699 / "nodes").mkdir(parents=True)
(lane699 / "route_receipts.json").write_text(json.dumps({"plans": f"anthropic/{DOT}"}))
r = wfmod._route_substitution_refusal({"_run": lane699},
                                      dict(node_dot, model=HY), spawn_no=2)
check("receipt hold: hyphenated re-spawn under dotted receipt is NOT a substitution",
      r is None, r)
r = wfmod._route_substitution_refusal({"_run": lane699},
                                      dict(node_dot, model=OTHER), spawn_no=2)
check("receipt hold: different model under the receipt is STILL denied",
      isinstance(r, dict) and r.get("error_class") == "route_substitution_denied", r)
# receipt file shape (the durable lane receipt) held to the same contract
run699 = Path(tmp_dir.name) / "run699"; (run699 / "nodes").mkdir(parents=True)
(run699 / "route_receipts.json").write_text(json.dumps({"plans": f"anthropic/{DOT}"}))
r = wfmod._route_substitution_refusal({"_run": run699},
                                      {"id": "plans", "type": "agent",
                                       "provider": "anthropic", "model": HY}, 3)
check("receipt hold (durable file): alias spelling re-spawn passes the receipt",
      r is None, r)
r = wfmod._route_substitution_refusal({"_run": run699},
                                      {"id": "plans", "type": "agent",
                                       "provider": "x", "model": OTHER}, 3)
check("receipt hold (durable file): different model still refused BEFORE submit",
      isinstance(r, dict) and r.get("error_class") == "route_substitution_denied", r)
check("receipt hold: absent receipt never fires",
      wfmod._route_substitution_refusal({"_run": Path(tmp_dir.name) / "nope"},
                                        {"id": "x", "provider": "a", "model": "m"}, 1) is None)

# ---- 3. door side: the submit-ping same-route law uses the SAME normalizer ------
door = importlib.import_module("__init__")
import wf_test_isolation as _iso71; _iso71.install(door)
door._CTX = None
door._seat_model_cfg = lambda: {"default": "seat-default", "aliases": {}}
door._seat_aliases = lambda: []
door._seat_default = lambda: "seat-default"
_spawned = []
door._spawn_runner = lambda r: _spawned.append(r.name)

# core records the ping route with ITS normalized (hyphenated) spelling; the
# pinned node is dotted. Under one contract the recorded route IS the pinned route.
check("door same-route law: hyphenated recorded route matches dotted pin",
      door._same_ping_route({"provider": "anthropic", "model": HY}, "anthropic", DOT))
check("door same-route law: dotted recorded route matches hyphenated pin",
      door._same_ping_route({"provider": "anthropic", "model": DOT}, "anthropic", HY))
check("door same-route law: different model on the pin is NOT same-route",
      not door._same_ping_route({"provider": "anthropic", "model": OTHER}, "anthropic", DOT))
check("door same-route law: provider mismatch is NOT same-route (gate intact)",
      not door._same_ping_route({"provider": "other", "model": DOT}, "anthropic", DOT))

def set_ping(behavior):
    if behavior is None:
        door._import_call_llm = lambda: (_ for _ in ()).throw(ImportError("No module named 'agent'"))
        return
    def call_llm(task=None, provider=None, model=None, messages=None, max_tokens=None,
                 timeout=None, route_info=None, **kw):
        if route_info is not None:
            route_info.update(behavior.get("record",
                                {"provider": str(provider or ""), "model": str(model or "")}))
        exc = behavior.get("raise_")
        if exc is not None:
            raise exc
        return "pong"
    door._import_call_llm = lambda: call_llm

class HTTP429(Exception): pass

def pinned_graph(**extra):
    n = {"id": "plans", "type": "agent", "goal": "x",
         "provider": "anthropic", "model": DOT}
    n.update(extra)
    return {"name": "p699", "nodes": [n]}

# alive pin under the dotted name bakes route_verified and launches
set_ping({"record": {"provider": "anthropic", "model": HY}})   # core answers normalized
out = door.act_run({"graph": pinned_graph()})
check("door: normalized ping answer on the pinned route counts ALIVE (launches, no refusal)",
      bool(out.get("run_id")), out)
if out.get("run_id"):
    gj = json.loads((Path(os.environ["WF_RUNS_ROOT"]) / out["run_id"] / "graph.json").read_text())
    check("door: alive pin bakes route_verified (require_route machinery intact)",
          gj["nodes"][0].get("route_verified") == f"anthropic/{DOT}", gj["nodes"][0])

# dead pin STILL refused — the gate is NOT softened
set_ping({"raise_": HTTP429("Error code: 429 - rate limited"),
          "record": {"provider": "anthropic", "model": HY}})
out = door.act_run({"graph": pinned_graph()})
check("dead pin still REFUSED at submit (gate not softened, no fallback enabled)",
      "error" in out and "route_unavailable at submit" in out.get("error", "")
      and DOT in out.get("error", ""), out)

# fallback-ladder surprise (different model recorded) STILL refused
set_ping({"record": {"provider": "openai", "model": "other-route-9"}})
out = door.act_run({"graph": pinned_graph()})
check("fallback-ladder surprise still REFUSED (wrong_route law intact)",
      "error" in out and "FALLBACK LADDER" in out.get("error", "").upper(), out)

# infra-absence stays unknown = launches
set_ping(None)
out = door.act_run({"graph": pinned_graph()})
check("core-absence never blocks (fail-open on absence unchanged)",
      bool(out.get("run_id")), out)

# ---- 4. provider boundaries: the same punctuation is NOT the same route off Anthropic ----
OAI, OAI_DOT, OAI_HY = "openai-codex", "model-5.1", "model-5-1"
check("door same-route law: openai-codex dotted pin vs hyphenated record is NOT same-route",
      not door._same_ping_route({"provider": OAI, "model": OAI_HY}, OAI, OAI_DOT))
check("door same-route law: openrouter cross-vendor (vendor-b/alpha vs pin vendor-a/alpha) is NOT same-route",
      not door._same_ping_route({"provider": "openrouter", "model": "vendor-b/alpha"}, "openrouter", "vendor-a/alpha"))
check("door same-route law: openrouter same vendor still same-route",
      door._same_ping_route({"provider": "openrouter", "model": "vendor-a/alpha"}, "openrouter", "vendor-a/alpha"))
before = len(_spawned)
set_ping({"record": {"provider": OAI, "model": OAI_HY}})
out = door.act_run({"graph": {"name": "p699b", "nodes": [{"id": "plans", "type": "agent", "goal": "x",
                                                         "provider": OAI, "model": OAI_DOT}]}})
check("door: openai-codex dotted pin answered by a hyphenated route is refused at submit, nothing spawned",
      "error" in out and "FALLBACK LADDER" in out.get("error", "").upper() and len(_spawned) == before, out)
out = wfmod._route_hold(meta, {"status": "done", "served_model": OAI_HY},
                        {"model": OAI_DOT, "provider": OAI, "route_verified": f"{OAI}/{OAI_DOT}"})
check("commit hold: openai-codex hyphenated billed vs dotted proof -> still route_unavailable",
      out.get("status") == "failed" and out.get("error_class") == "route_unavailable", out)
set_ping({"record": {"provider": OAI, "model": OAI_HY}})
check("quota recovery probe: a hyphenated answer for a dotted provider-less stamp is NOT a recovery",
      door._ping_reachable(OAI_DOT) is False)
set_ping({"record": {"provider": "anthropic", "model": HY}})
check("quota recovery probe: Anthropic-qualified stamp answered under the normalized spelling recovers",
      door._ping_reachable(f"anthropic/{DOT}") is True)
(run699 / "route_receipts.json").write_text(json.dumps({"plans": f"{OAI}/{OAI_DOT}"}))
r = wfmod._route_substitution_refusal({"_run": run699}, {"id": "plans", "type": "agent", "provider": OAI, "model": OAI_HY}, 5)
check("receipt hold (durable file): openai-codex hyphenated re-spawn under a dotted receipt is denied",
      isinstance(r, dict) and r.get("error_class") == "route_substitution_denied", r)

# ---- 5. review of #296: the overbroad-fold counterexamples die at the commit hold ----
for served, pin in ((UNDER, HY), ("m..1", "m-1"), ("model-5.4", "model-5-4"), (BEDROCK_DOT, BEDROCK_HY)):
    out = wfmod._route_hold(meta, {"status": "done", "served_model": served},
                            {"model": "pin-x", "provider": "anthropic", "route_verified": f"anthropic/{pin}"})
    check(f"commit hold: {served!r} billed vs {pin!r} proved -> route_unavailable",
          out.get("status") == "failed" and out.get("error_class") == "route_unavailable", out)
out = wfmod._route_hold(meta, {"status": "done", "served_model": OTHER}, PROOF)
check("commit hold: cross-model control still route_unavailable",
      out.get("status") == "failed" and out.get("error_class") == "route_unavailable", out)

# ---- 6. review of #296 (P1b): a cross-provider receipt is refused BEFORE any folding ----
(run699 / "route_receipts.json").write_text(json.dumps({"plans": f"{OAI}/{OAI_DOT}"}))
r = wfmod._route_substitution_refusal({"_run": run699}, {"id": "plans", "type": "agent", "provider": "anthropic", "model": OAI_HY}, 6)
check("receipt hold: openai-codex receipt + anthropic node of the folded spelling -> denied",
      isinstance(r, dict) and r.get("error_class") == "route_substitution_denied", r)
check("route_provider: receipt provider governs; a node/receipt provider split folds nothing",
      wc.route_provider({"provider": "anthropic"}, f"{OAI}/{OAI_DOT}") == ""
      and wc.route_provider({"provider": "anthropic"}, f"anthropic/{DOT}") == "anthropic"
      and wc.route_provider({}, f"anthropic/{DOT}") == "anthropic")

# ---- 7. review of #296 (P1 required repair): a literal '(suffix)' is NEVER peeled
# Stock core preserves literal model suffixes and records the concrete model
# verbatim; suffix peeling is unsupported display-label normalization. Both
# directions, through submit, commit hold, durable receipt and quota recovery.
check("P1 submit: openai-codex pin 'model-1' vs recorded 'model-1(extra)' is NOT same-route",
      not door._same_ping_route({"provider": OAI_PRE, "model": SUF_ON}, OAI_PRE, SUF_OFF))
check("P1 submit: openai-codex pin 'model-1(extra)' vs recorded 'model-1' is NOT same-route",
      not door._same_ping_route({"provider": OAI_PRE, "model": SUF_OFF}, OAI_PRE, SUF_ON))
before = len(_spawned)
set_ping({"record": {"provider": OAI_PRE, "model": SUF_ON}})
out = door.act_run({"graph": {"name": "p699s", "nodes": [{"id": "plans", "type": "agent", "goal": "x",
                                                         "provider": OAI_PRE, "model": SUF_OFF}]}})
check("P1 submit end-to-end: suffixed ping answer for a bare pin is REFUSED, nothing spawned",
      "error" in out and "FALLBACK LADDER" in out.get("error", "").upper()
      and len(_spawned) == before, out)
for served, pin, prov in ((SUF_ON, SUF_OFF, OAI_PRE),
                          (SUF_OFF, SUF_ON, OAI_PRE),
                          (DOT + "(extra)", HY, "anthropic")):
    out = wfmod._route_hold(meta, {"status": "done", "served_model": served},
                            {"model": pin, "provider": prov,
                             "route_verified": f"{prov}/{pin}"})
    check(f"P1 commit hold: {served!r} billed vs {pin!r} proved -> route_unavailable",
          out.get("status") == "failed" and out.get("error_class") == "route_unavailable", out)
run699s = Path(tmp_dir.name) / "run699s"; (run699s / "nodes").mkdir(parents=True)
(run699s / "route_receipts.json").write_text(json.dumps({"plans": f"{OAI_PRE}/{SUF_ON}"}))
r = wfmod._route_substitution_refusal({"_run": run699s}, {"id": "plans", "type": "agent",
                                                         "provider": OAI_PRE, "model": SUF_OFF}, 7)
check("P1 durable receipt: bare re-spawn under a suffixed receipt is DENIED",
      isinstance(r, dict) and r.get("error_class") == "route_substitution_denied", r)
(run699s / "route_receipts.json").write_text(json.dumps({"plans": f"{OAI_PRE}/{SUF_OFF}"}))
r = wfmod._route_substitution_refusal({"_run": run699s}, {"id": "plans", "type": "agent",
                                                         "provider": OAI_PRE, "model": SUF_ON}, 8)
check("P1 durable receipt: suffixed re-spawn under a bare receipt is DENIED",
      isinstance(r, dict) and r.get("error_class") == "route_substitution_denied", r)
set_ping({"record": {"provider": OAI_PRE, "model": SUF_ON}})
check("P1 quota recovery: a suffixed answer for a bare stamp is NOT a recovery",
      door._ping_reachable(f"{OAI_PRE}/{SUF_OFF}") is False)
set_ping({"record": {"provider": OAI_PRE, "model": SUF_OFF}})
check("P1 quota recovery: a bare answer for a suffixed stamp is NOT a recovery",
      door._ping_reachable(f"{OAI_PRE}/{SUF_ON}") is False)

sys.exit(1 if fails else 0)
