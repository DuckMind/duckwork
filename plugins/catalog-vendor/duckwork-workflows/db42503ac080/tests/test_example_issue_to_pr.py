#!/usr/bin/env python3
"""issue-to-pr example gate (Core-10 authoring contract).

The template's teaching laws are STRUCTURAL: abort-before-investment only exists
if the halt gates are complementary and every expensive node hangs behind the
work route; the baseline-then-delta law only exists if baseline precedes fix AND
verify declares baseline in inputs; cleanup is only honest if it hangs on BOTH
the publish path and the halt arms. Those are shape facts — assert them here,
cold, without spawning anything. Run directly: prints PASS lines, exits non-zero
on the first broken contract.
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

GRAPH = ROOT / "examples" / "release" / "issue-to-pr.workflow.json"

# scrub mirror: run scripts/make_public.py's OWN merged audit pattern over the
# shipped bytes (import by FILE LOCATION, same law as test_example_census_fanout).
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
check(g.get("grammar") == "wf/1" and g.get("name") == "issue-to-pr",
      "wf/1 grammar, name issue-to-pr")

nodes = {n["id"]: n for n in g["nodes"]}

# --- abort-before-investment: complementary gate pair on intake.actionable ---
rw, rh = nodes["route-work"], nodes["route-halt"]
check(rw["type"] == "gate" and rh["type"] == "gate"
      and rw["when"] == "out.intake.actionable == True"
      and rh["when"] == "out.intake.actionable == False"
      and rw.get("on_skip") == "prune" and rh.get("on_skip") == "prune",
      "route-work/route-halt are a complementary prune pair on the classifier's boolean")
order = [n["id"] for n in g["nodes"]]
# every expensive node is downstream of route-work via the route-work -> baseline chain
check(nodes["baseline"]["after"] == ["route-work"],
      "baseline (the first expensive step) hangs ONLY on route-work — abort happens before investment")
for expensive in ("fix", "verify", "review", "publish"):
    seen, frontier = set(), ["baseline"]
    while frontier:
        nid = frontier.pop()
        for m in g["nodes"]:
            if nid in m.get("after", []) and m["id"] not in seen:
                seen.add(m["id"]); frontier.append(m["id"])
    check(expensive in seen, f"{expensive} is downstream of the work route (never first-wave)")
check(nodes["halt-notice"]["type"] == "echo" and nodes["halt-notice"]["after"] == ["route-halt"],
      "the halt arm carries its why as an echo (a constant travels as echo, not a spawn)")

# --- baseline-then-delta: baseline precedes fix; verify reads the baseline record ---
check(nodes["fix"]["after"] == ["baseline"],
      "fix hangs ONLY on baseline (the gate pair sits above baseline)")
check("baseline" in nodes["verify"]["inputs"] and "intake" in nodes["verify"]["inputs"],
      "verify declares inputs: the baseline record AND intake (delta law needs both)")
check("pre_existing" in nodes["baseline"]["schema"]["properties"]
      and "pre_existing" in nodes["baseline"]["schema"]["required"],
      "baseline's schema makes the pre-existing failure set a REQUIRED field")
check("verdict" in nodes["verify"]["schema"]["properties"]
      and "regressed" in json.dumps(nodes["verify"]["schema"]["properties"]["verdict"]),
      "verify's verdict enum names regressed (a new failure can never read as clean)")

# --- verify halts the lane on non-clean: complementary pair, echo halt arm ---
rv, rr = nodes["route-verified"], nodes["route-regressed"]
check(rv["when"] == "out.verify.verdict == 'clean'"
      and rr["when"] == "out.verify.verdict != 'clean'"
      and rv.get("on_skip") == "prune" and rr.get("on_skip") == "prune",
      "route-verified/route-regressed are a complementary prune pair on the verifier verdict")
check(nodes["verify-halt"]["type"] == "echo" and nodes["verify-halt"]["after"] == ["route-regressed"],
      "the verify halt arm is an echo behind its own gate (a prune-path echo behind the PASSING gate never fires — the bug this pair kills)")

# --- the human gate stands before anything leaves the machine ---
check(nodes["approve"]["type"] == "gate" and "publish" in nodes["approve"]["options"]
      and "hold" in nodes["approve"]["options"] and nodes["approve"]["after"] == ["review"],
      "approve is a human gate (publish|hold) directly behind review")
check("not approved" in nodes["publish"]["goal"],
      "publish executes only the approved option and reports 'not approved' otherwise")

# --- cleanup walks every arm ---
ca = set(nodes["cleanup"]["after"])
check({"publish", "halt-notice", "verify-halt"} <= ca,
      "cleanup hangs on the publish path AND both halt arms (the lane state is reported whichever arm ran)")
check(nodes["cleanup"].get("after_partial") is True,
      "cleanup harvests off a partial ancestor (a report must never darken on a dead join)")

# --- prune-safe inputs law: no hard inputs ref onto a node the halt arms prune ---
prunable = {"baseline", "fix", "verify", "review", "publish", "approve",
            "route-work", "route-verified", "route-regressed"}
for n in g["nodes"]:
    for ref in n.get("inputs", []):
        head = ref.split(".")[0]
        # inputs onto a prunable node are legal ONLY if that node is in n's after
        # (an after-edge to a skipped dep still schedules when another dep is
        # live, but the INPUT would be missing at spawn); census lesson: keep
        # joins reading parents, not arm siblings.
        check(head not in prunable or head in n.get("after", []) or n["id"] in ("verify", "review"),
              f"{n['id']}: inputs ref '{ref}' is prune-safe", detail=str(n.get("after")))

# budgets ride explicit small numbers; nothing pins a model/tier
baked = wfcommon.apply_graph_defaults(copy.deepcopy(g))["nodes"]
check(all("model" not in n and "tier" not in n and "provider" not in n for n in baked),
      "baked graph resolves no explicit model: seat defaults own routing")

print(f"OK issue-to-pr: {ok} checks passed")
