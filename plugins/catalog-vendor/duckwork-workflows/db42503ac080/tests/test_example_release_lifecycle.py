#!/usr/bin/env python3
"""release-lifecycle example gate (Core-10 authoring contract).

The template's teaching laws are STRUCTURAL: the halt decision and the drift
decision must each be a complementary prune-gate pair; the publish arm must sit
behind the green machine check AND a human gate; the await-ci gate must be a
machine park whose argv is FIXED (a seed must not be able to smuggle shell into
a process argument); the publication fan-out must be a barrier (no quorum) whose
intake head sits in its own after (prune law). Assert cold, no spawns. Run
directly: prints PASS lines, exits non-zero on the first broken contract.
"""
import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

GRAPH = ROOT / "examples" / "release" / "release-lifecycle.workflow.json"

import importlib.util as _ilu
_mp_spec = _ilu.spec_from_file_location("make_public", ROOT / "scripts" / "make_public.py")
assert _mp_spec and _mp_spec.loader, "scripts/make_public.py must exist"
make_public = _ilu.module_from_spec(_mp_spec)
_mp_spec.loader.exec_module(make_public)
SCRUB = make_public.load_scrub_list(ROOT)

ok = 0


def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}" + (f"  << {detail}" if detail and cond is not True else "")
    ok += 1
    print(f"PASS {msg}")


raw = GRAPH.read_text(encoding="utf-8")
g = json.loads(raw)

check(SCRUB.search(raw) is None,
      "shipped bytes carry zero scrub hits (no estate vocab, no vendor/estate model names)")
check(not any("model" in n for n in g["nodes"]) and "model" not in g.get("defaults", {}),
      "no node pins a model: every child rides the seat default")
check(g.get("grammar") == "wf/1" and g.get("name") == "release-lifecycle",
      "wf/1 grammar, name release-lifecycle")

nodes = {n["id"]: n for n in g["nodes"]}

# --- preflight halt pair ---
rg, rh = nodes["route-go"], nodes["route-halt"]
check(rg["when"] == "out.preflight.proceed == True"
      and rh["when"] == "out.preflight.proceed == False"
      and rg.get("on_skip") == "prune" and rh.get("on_skip") == "prune",
      "route-go/route-halt are a complementary prune pair on the preflight boolean")
check(nodes["halt-notice"]["type"] == "echo" and nodes["halt-notice"]["after"] == ["route-halt"],
      "the preflight halt arm is an echo behind ITS gate (behind the passing gate it would never fire)")

# --- the maker never grades its own work: prep changes, verify re-runs the gate ---
check(nodes["prep"]["after"] == ["route-go"],
      "prep hangs only on the go-route (nothing expensive before preflight passes)")
check("{run.check_command}" in nodes["verify"]["goal"]
      and "INDEPENDENTLY" in nodes["verify"]["goal"],
      "verify re-runs the machine gate itself in a separate node (self-report is not proof)")

# --- drift halt pair; nothing publishes on drift ---
rc, rd = nodes["route-consistent"], nodes["route-drift"]
check(rc["when"] == "out.verify.verdict == 'verified'"
      and rd["when"] == "out.verify.verdict != 'verified'"
      and rc.get("on_skip") == "prune" and rd.get("on_skip") == "prune",
      "route-consistent/route-drift are a complementary prune pair on the verifier verdict")
check(nodes["drift-halt"]["type"] == "echo" and nodes["drift-halt"]["after"] == ["route-drift"],
      "the drift halt arm is an echo behind its own gate")
check("re-bump" in nodes["drift-halt"]["output"]["note"] or "re-running" in nodes["drift-halt"]["output"]["note"],
      "the drift halt echo names the trap: never blindly re-run the bump over drifted state")

# --- publish order: human gate AFTER the green check, BEFORE the command runs ---
check(nodes["approve"]["type"] == "gate" and nodes["approve"]["after"] == ["route-consistent"]
      and set(nodes["approve"]["options"]) == {"publish", "hold"},
      "approve (publish|hold) sits directly behind the consistency route")
check(nodes["publish"]["after"] == ["approve"],
      "publish hangs on the human gate - the tag/push can never precede the answer")
check("{run.publish_command}" in nodes["publish"]["goal"]
      and "not approved" in nodes["publish"]["goal"],
      "publish runs the named command only on approval")

# --- the handoff machine gate: FIXED argv, zero seeds inside it ---
aw = nodes["await-ci"]
check(aw["type"] == "gate" and "until_argv" in aw["wait"],
      "await-ci is a machine gate (until_argv park, zero tokens while waiting)")
# the probe is EXECUTED CODE, not prose: it must compile (a comment edit once
# replaced the try:/sys.exit() lines and left an orphaned except — the string
# checks below all stayed green while the gate could never run: this is the pin).
try:
    compile(aw["wait"]["until_argv"][2], "<await-ci-probe>", "exec")
    _probe_compiled = True
except SyntaxError as _e:
    _probe_compiled = False
    print(f"  probe SyntaxError: {_e}")
check(_probe_compiled, "await-ci probe PYTHON COMPILES (executed code, not just prose)")
argv_blob = json.dumps(aw["wait"]["until_argv"])
check("{run." not in argv_blob,
      "the gate argv carries NO {run.*} seed: the check command travels via the handoff file, never as substituted shell")
check("ci_check.txt" in argv_blob and "POINTER" in argv_blob.upper() or "current" in argv_blob,
      "the fixed probe reads a pointer -> handoff file (the command is DATA)")
check(aw["wait"].get("every_s") and aw["wait"].get("timeout_s"),
      "the park declares cadence and a deadline (a gate that can never expire is a hang)")
check("sys.exit(2)" in argv_blob,
      "a missing/broken handoff exits 2 (non-zero): a missing handoff is NEVER green")

# --- publication barrier: every channel answered or named missing ---
fo = nodes["verify-channels"]["fanout"]
check("quorum" not in fo,
      "the channel fan-out sets NO quorum - a release claim is a barrier, not a race")
check(fo["items_from"] == "channel-intake.items"
      and "channel-intake" in nodes["verify-channels"]["after"],
      "items flow from the intake record and the intake head sits in the fan-out's own after")
fs = nodes["verify-channels"]["schema"]
check(sorted(fs.get("required", [])) == ["channel", "live"],
      "each channel answers the per-item contract {channel, live}")
co = nodes["closeout"]
check({"halt-notice", "drift-halt"} <= set(co["after"]),
      "the closeout sees both halt arms (a halted release still gets its record)")
check(co.get("after_partial") is True,
      "the closeout harvests off partial joins - a damaged tally must not darken the release")

# --- publish ordering law lives in the prep goal ---
check("Do NOT tag" in nodes["prep"]["goal"].upper() or "NEVER" in nodes["prep"]["goal"].upper(),
      "the no-tag-before-publish law is baked where the bump happens (prep), not only downstream")

# --- item interpolation law: {item.channel}/{item.check} bind against intake-shaped
#     dict items, since the fan-out carries no goal override ---
import wf  # noqa: E402
check("{channel}" in nodes["verify-channels"]["goal"] and "{item." not in nodes["verify-channels"]["goal"],
      "the fan-out prompt binds dict fields as BARE {FIELD} (dotted {item.field} never interpolates - fmt_goal law)")
sample = {"channel": "c", "check": "true"}
rendered = wf.fmt_goal(nodes["verify-channels"]["goal"], sample, 0)
check(not wf._dangling_placeholders(rendered, sample),
      "the channel lane prompt renders with zero dangling placeholders")

# every {run.KEY} the goals reference must be named in the description contract
desc = g["description"]
keys = set(re.findall(r"\{run\.([a-z_]+)\}", json.dumps(g["nodes"])))
check(keys and all(k in desc for k in keys),
      "every seed key used in prompts is documented in the description",
      detail=str(sorted(k for k in keys if k not in desc)))

baked = wfcommon.apply_graph_defaults(copy.deepcopy(g))["nodes"]
check(all("model" not in n and "tier" not in n and "provider" not in n for n in baked),
      "baked graph resolves no explicit model: seat defaults own routing")

print(f"OK release-lifecycle: {ok} checks passed")
