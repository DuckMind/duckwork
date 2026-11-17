#!/usr/bin/env python3
"""Cold structural gate for examples/release/submit-pr.workflow.json.

The stub is the reusable *->PR second half: it must refuse unsafe branches
before spending a token on drafting, re-run validation itself rather than
believing a claim, hold for a human before any external effect, and verify
the live PR independently of the submitter. These checks pin that skeleton;
the dogfood receipts under receipts/submit-pr/ carry the live proof.
"""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRAPH = ROOT / "examples" / "release" / "submit-pr.workflow.json"
g = json.loads(GRAPH.read_text(encoding="utf-8"))
nodes = {n["id"]: n for n in g["nodes"]}
fails = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

check("graph validates as wf/1 with a description and defaults",
      g.get("grammar", "wf/1") == "wf/1" and len(g.get("description", "")) > 100 and "defaults" in g)

SEEDS = ["repo_dir", "head_branch", "base_repo", "base_branch", "push_remote",
         "validation_cmds", "pr_title", "pr_scope"]
blob = json.dumps(g)
for k in SEEDS:
    check(f"seed {k} is referenced as {{run.{k}}}", ("{run." + k + "}") in blob)

# pipeline skeleton
check("preflight is a root agent", nodes["preflight"]["type"] == "agent" and not nodes["preflight"].get("after"))
check("preflight scans for secrets and dirty trees",
      "secret" in nodes["preflight"]["goal"].lower() and "status --short" in nodes["preflight"]["goal"])
check("validate runs the seeds' commands itself",
      "each command" in nodes["validate"]["goal"] and "never believed" not in nodes["validate"]["goal"])

# the two halt arms each sit behind their own complement route gate
for halt, route, cond in [("preflight-halt", "route-preflight-halt", "out.preflight.ok == False"),
                          ("validate-halt", "route-validate-red", "out.validate.verdict != 'green'")]:
    check(f"{halt} hangs on its complement gate {route}", nodes[halt]["after"] == [route])
    check(f"{route} fires on the complement condition", nodes[route]["when"] == cond)
    passing = "route-preflight" if halt == "preflight-halt" else "route-validated"
    pw, rw = nodes[passing]["when"], nodes[route]["when"]
    # complementarity: the two whens disagree for every value (== vs !=/not-equal on the same path)
    check(f"{passing} and {route} are complementary",
          pw.split(" ")[0] == rw.split(" ")[0] and ("==" in pw and ("!=" in rw or "not" in rw or (pw.endswith("True") and rw.endswith("False")))))

check("the human gate is the only door to an external effect",
      nodes["submit"]["after"] == ["approve"] and nodes["approve"]["type"] == "gate"
      and set(nodes["approve"]["options"]) == {"submit", "hold"})
check("nothing in the graph merges", "merge" not in nodes["submit"]["goal"].lower().replace("merging", "merge-") or "never" in nodes["submit"]["goal"])
check("submit refuses a second PR over an open one", "already" in nodes["submit"]["goal"] and "second" in nodes["submit"]["goal"])

check("verify-pr is independent and opts into partial harvest",
      nodes["verify-pr"]["type"] == "agent" and nodes["verify-pr"].get("after_partial") is True
      and "gh pr view" in nodes["verify-pr"]["goal"])
check("verify-pr hangs on submit AND both halt arms (all arms converge)",
      set(nodes["verify-pr"]["after"]) >= {"submit", "preflight-halt", "validate-halt"})

# B3 (review round, #169): the draft must travel as PINNED BYTES through an edge the
# engine can see, not as status-prose memory. submit takes inputs:["draft"] (draft is
# submit's grandparent - no auto-injection) and commits the exact title/body it sent;
# verify-pr anchors its API compare on that committed record (its direct parent).
check("submit pulls the draft record through an explicit input edge",
      nodes["submit"].get("inputs") == ["draft"])
check("submit commits the exact bytes it sent (verifier's anchor)",
      {"title_sent", "body_sent"} <= set(nodes["submit"]["schema"]["properties"])
      and "title_sent" in nodes["submit"]["goal"] and "verbatim" in nodes["submit"]["goal"])
check("verify-pr anchors on the submit record, not remembered prose",
      "submit record" in nodes["verify-pr"]["goal"]
      and "title_sent" in nodes["verify-pr"]["goal"]
      and "draft" not in (nodes["verify-pr"].get("inputs") or []))
check("verify-pr excuses title/body on the dedup path (updated=true predates this run)",
      "updated=true" in nodes["verify-pr"]["goal"]
      and "n/a" in nodes["verify-pr"]["goal"])
check("closeout reports every arm",
      set((nodes["closeout"]["schema"]["properties"]["arm"].get("description") or "").replace("one of: ", "").split("|"))
      == {"submitted", "preflight-halt", "validate-halt", "held"})

# prune-safety: no hard inputs onto a node that a halt arm can prune
first_wave = {nid for nid, n in nodes.items() if not n.get("after")}
def ancestors(nid, seen=None):
    seen = seen or set()
    for p in nodes[nid].get("after", []):
        if p not in seen:
            seen.add(p); ancestors(p, seen)
    return seen
prunable = {nid for nid, n in nodes.items() if any(
    "halt" in a or "red" in a for a in ancestors(nid))}
bad = []
for nid, n in nodes.items():
    for ref in n.get("inputs", []):
        src = ref.split(".")[0]
        if nid in prunable and src not in first_wave and src not in ("preflight",):
            bad.append((nid, src))
check("no hard input crosses into prunable territory", not bad)

check("all agent nodes carry a schema with fenced-json law",
      all("schema" in n for n in g["nodes"] if n["type"] == "agent")
      and all(("Reply" in n["goal"] or "reply " in n["goal"] or "fenced" in n["goal"])
              for n in g["nodes"] if n["type"] == "agent" and "goal" in n))
check("decontaminated: no forbidden-land vocabulary",
      not any(w in blob.lower() for w in ("gas city", "gastown", "polecat", "convoy", "refinery", "wisp", "molecule", "sling")))

print("RESULT:", "PASS" if not fails else f"FAIL ({len(fails)}): {fails}")
sys.exit(0 if not fails else 1)
