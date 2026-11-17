"""expand_includes / include_provenance core-resolver contracts (design
2026-09-30). Pure-Python, duckwork-free: a dict library_reader is
injected, the door is never imported. Pins:
  (1) deterministic alias__id namespacing; ID_OK/64-cap REFUSE (never truncate),
      no dots in generated ids.
  (2) the five id-ref surfaces rewritten inside the subtree IN LOCKSTEP: after,
      inputs heads, requires keys, fanout.items_from head + its after entry, and
      when out.<id>. paths — with when heads existence-checked by the resolver
      itself (the validator never checks them).
  (3) nested includes expand inner-first (A -> B -> C), strip-on-expand is a byte
      guarantee, and a graph without includes passes through untouched.
  (4) every guard REFUSES with a named ValueError: missing/unknown entry, cycle,
      alias collision, id collision, depth cap, merged node/byte caps, unbound
      seed, exports misnaming.
  (5) exports map public names -> namespaced ids at parent ref sites; literal
      alias__id refs work without exports; BARE inner ids in the parent REFUSE.
  (6) seed rendering is scoped: {run.KEY} inside the included subtree only — the
      parent's refs are never consumed by include seeds and vice versa.
  (7) shared fixed-scratch-path detection emits notes[] (warn, never rewrite).
  (8) efp stability: a parent node untouched by expansion keeps its def_hash/efp
      byte-for-byte; a rewired node's fingerprint moves (the intended granularity).
"""
import copy, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wfcommon  # noqa: E402

fails = 0
ok = 0


def check(cond, label, detail=""):
    global fails, ok
    if cond:
        ok += 1
        print("PASS", label)
    else:
        fails += 1
        print("FAIL", label, f" << {detail}" if detail else "")


def refuses(label, graph, reader, *needles):
    try:
        wfcommon.expand_includes(graph, reader)
    except ValueError as e:
        msg = str(e)
        check(all(n in msg for n in needles), label, f"message {msg!r} missing a needle")
        return msg
    except Exception as e:  # wrong exception class is a FAIL, not a crash
        check(False, label, f"raised {type(e).__name__}: {e}")
        return str(e)
    check(False, label, "no ValueError raised")
    return ""


# ---------------- fixtures ----------------
def agent(nid, **kw):
    return {"id": nid, "type": "agent", "goal": f"goal of {nid}", **kw}


def gate(nid, **kw):
    return {"id": nid, "type": "gate", "question": f"q {nid}", **kw}


def echo(nid, **kw):
    return {"id": nid, "type": "echo", "output": {"o": nid}, **kw}


# a rich included graph exercising all five surfaces internally
REVIEW = {
    "name": "review",
    "nodes": [
        agent("kick"),
        agent("fan", after=["kick"], fanout={"items_from": "kick.items",
                                             "goal": "check {run.artifact}"}),
        agent("seat", after=["kick"], inputs=["kick.summary"],
              requires={"kick": ["summary"]}, context="review {run.artifact}"),
        gate("approve", after=["seat"], when="out.seat.ok == True and out.kick.done"),
    ],
}
LIB = {"review": REVIEW}


def reader(name):
    return copy.deepcopy(LIB.get(name))


byids = lambda g: {n["id"]: n for n in g["nodes"]}


# ---------------- (1) namespacing ----------------
g = {"name": "meta", "include": [{"as": "rev", "use": "review",
                                  "seeds": {"artifact": "/abs/p"}}],
     "nodes": [agent("prep")]}
exp, notes = wfcommon.expand_includes(g, reader)
check(sorted(n["id"] for n in exp["nodes"]) ==
      ["prep", "rev__approve", "rev__fan", "rev__kick", "rev__seat"],
      "ids namespaced deterministically alias__inner", exp["nodes"])
check(all(wfcommon.ID_OK.match(n["id"]) and "." not in n["id"]
          for n in exp["nodes"]), "every generated id satisfies ID_OK with no dots")
check(notes == [], "clean include produces no notes", notes)

# overflow: alias 24 + sep 2 + inner 39 = 65 > 64 — REFUSE, never truncate
LIB["wide"] = {"name": "wide", "nodes": [agent("z" * 39)]}
refuses("64-char overflow refuses, never truncates",
        {"name": "m", "include": [{"as": "a" * 24, "use": "wide"}], "nodes": []},
        reader, "invalid", "64")
# dot in an inner id: generated id would carry a dot -> refuse (dot is out.<id> syntax)
LIB["dotty"] = {"name": "dotty", "nodes": [agent("no.de")]}
refuses("dot-in-inner-id generated id refused",
        {"name": "m", "include": [{"as": "d", "use": "dotty"}], "nodes": []},
        reader, "no dots")


# ---------------- (2) five surfaces, in lockstep ----------------
n_ = byids(exp)
check(n_["rev__fan"]["after"] == ["rev__kick"]
      and n_["rev__fan"]["fanout"]["items_from"] == "rev__kick.items",
      "items_from head + its after entry rewritten IN LOCKSTEP")
check(n_["rev__seat"]["inputs"] == ["rev__kick.summary"], "inputs head rewritten")
check(n_["rev__seat"]["requires"] == {"rev__kick": ["summary"]}, "requires key rewritten")
check(n_["rev__approve"]["when"] == "out.rev__seat.ok == True and out.rev__kick.done",
      "when out.<id>. heads rewritten", n_["rev__approve"]["when"])
check(wfcommon.validate_graph_errors(exp) == [],
      "expanded composite passes the UNTOUCHED closed-set validator",
      wfcommon.validate_graph_errors(exp))
# when heads are NOT checked by the validator -> the resolver must catch them itself
LIB["dangling"] = {"name": "dangling",
                   "nodes": [gate("gr", when="out.ghost.ok == True")]}
refuses("dangling when head in included graph refuses (validator would miss it)",
        {"name": "m", "include": [{"as": "x", "use": "dangling"}], "nodes": []},
        reader, "when", "ghost")


# ---------------- (3) inner-first + strip-on-expand ----------------
LIB["b"] = {"name": "b", "include": [{"as": "c", "use": "review"}], "nodes": [agent("bt")]}
LIB["a"] = {"name": "a", "include": [{"as": "b", "use": "b"}], "nodes": [agent("at")]}
exp3, _ = wfcommon.expand_includes(
    {"name": "m", "include": [{"as": "a", "use": "a"}], "nodes": []}, reader)
check(sorted(n["id"] for n in exp3["nodes"]) ==
      ["a__at", "a__b__bt", "a__b__c__approve", "a__b__c__fan",
       "a__b__c__kick", "a__b__c__seat"],
      "A->B->C expands inner-first with stacked namespaces", [n["id"] for n in exp3["nodes"]])
check(all(wfcommon.ID_OK.match(n["id"]) for n in exp3["nodes"])
      and wfcommon.validate_graph_errors(exp3) == [],
      "nested expansion stays in-grammar and validates clean")

# strip-on-expand: byte-level — no include key anywhere, other keys survive as-is
check("include" not in exp and "include" not in exp3, "include key stripped from expanded output")
raw = json.dumps(exp, sort_keys=True)
check("include" not in raw.replace("frontier", ""), "no include residue in serialized bytes")
check(exp.get("name") == "meta", "sibling top-level keys survive the strip")
# no-include graph: untouched pass-through, author graph not mutated
plain = {"name": "plain", "nodes": [agent("p1"), gate("g1", after=["p1"])]}
snapshot = copy.deepcopy(plain)
expp, notep = wfcommon.expand_includes(plain, reader)
check(json.dumps(expp, sort_keys=True) == json.dumps(snapshot, sort_keys=True)
      and notep == [] and plain == snapshot,
      "include-free graph expands to byte-identical output (golden-solo pin)")


# ---------------- (4) guard refusals ----------------
refuses("unknown library entry refused",
        {"name": "m", "include": [{"as": "z", "use": "nope"}], "nodes": [agent("p")]},
        reader, "z", "nope")
refuses("alias collision refused",
        {"name": "m", "include": [{"as": "z", "use": "review", "seeds": {"artifact": "/x"}},
                                  {"as": "z", "use": "review", "seeds": {"artifact": "/y"}}],
         "nodes": []}, reader, "duplicate alias", "z")
refuses("cycle A->B->A refused",
        {"name": "m", "include": [{"as": "a", "use": "cycle-a"}], "nodes": []},
        lambda nm: {"name": nm,
                    "include": [{"as": "r", "use": "cycle-a" if nm == "cycle-b" else "cycle-b"}],
                    "nodes": [agent("q")]}.get(nm) and
        {"name": nm,
         "include": [{"as": "r", "use": "cycle-a" if nm == "cycle-b" else "cycle-b"}],
         "nodes": [agent("q")]},
        "cycle")
# self-include
refuses("self-include refused", {"name": "m", "include": [{"as": "s", "use": "m-self"}],
                                 "nodes": []},
        lambda nm: {"name": nm, "include": [{"as": "t", "use": "m-self"}], "nodes": [agent("q")]},
        "cycle")
# id collision: parent already owns a namespaced id
refuses("namespaced id collides with a parent id",
        {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"}}],
         "nodes": [agent("rev__kick")]}, reader, "collides", "rev__kick")
# alias__id namespace collision across two includes of the SAME graph under... different
# aliases cannot collide by construction; same alias is covered by alias-collision above.
# depth cap: e1 -> e2 -> e3 -> e4 -> e5 is depth 5 > 4
depth_reader = lambda nm: ({"name": nm,
                            "include": [{"as": f"i{int(nm[1:]) + 1}",
                                         "use": f"e{int(nm[1:]) + 1}"}],
                            "nodes": []} if int(nm[1:]) < 5
                           else {"name": nm, "nodes": [agent("leaf")]})
refuses("depth cap 4 enforced",
        {"name": "m", "include": [{"as": "i1", "use": "e1"}], "nodes": []},
        depth_reader, "depth", "4")
# included graph fails standalone validation
LIB["broken"] = {"name": "broken", "nodes": [{"id": "x", "type": "agent"}]}  # no goal
refuses("included graph failing validation refuses",
        {"name": "m", "include": [{"as": "q", "use": "broken"}], "nodes": []},
        reader, "validate", "goal")
# unbound seed: subtree references {run.artifact}, seeds map lacks it
refuses("unbound {run.KEY} in subtree fails closed, naming the alias",
        {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"other": "1"}}],
         "nodes": []}, reader, "rev", "unbound", "artifact")
# seed value with braces rejected (existing fan-out guard extended to include seeds)
refuses("seed value containing braces refused",
        {"name": "m", "include": [{"as": "rev", "use": "review",
                                   "seeds": {"artifact": "{run.x}"}}], "nodes": []},
        reader, "braces")
# malformed directive shapes
refuses("include not a list refused",
        {"name": "m", "include": {"as": "a", "use": "review"}, "nodes": []}, reader, "non-empty list")
refuses("include empty list refused",
        {"name": "m", "include": [], "nodes": []}, reader, "non-empty list")
refuses("unknown include key refused",
        {"name": "m", "include": [{"as": "a", "use": "review", "alias2": "x"}], "nodes": []},
        reader, "unknown key", "as")
refuses("bad alias (dot) refused",
        {"name": "m", "include": [{"as": "a.b", "use": "review"}], "nodes": []}, reader, "alias")
# merged node-count cap (patch the constant, restore after)
saved = wfcommon.INCLUDE_NODES_MAX
wfcommon.INCLUDE_NODES_MAX = 3
try:
    refuses("merged node-count cap enforced",
            {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"}}],
             "nodes": [agent("p1"), agent("p2")]}, reader, "node-count cap")
finally:
    wfcommon.INCLUDE_NODES_MAX = saved
saved_b = wfcommon.INCLUDE_BYTES_MAX
wfcommon.INCLUDE_BYTES_MAX = 200
try:
    refuses("merged bytes cap enforced",
            {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"}}],
             "nodes": [agent("p1")]}, reader, "size cap")
finally:
    wfcommon.INCLUDE_BYTES_MAX = saved_b
# the caps are re-measured on the FINAL fused graph, after the parent-ref rewrite
# (the pre-rewrite candidate is compact-dump and shorter than the committed form:
# a cap between the two must refuse with the after-rewrite message, not pass)
g7 = {"name": "m", "include": [{"as": "rev", "use": "review",
                                "exports": {"approve": "ap"}}],
      "nodes": [agent("tail", after=["ap", "rev__seat"], inputs=["ap.answer"])]}
_exp7, _ = wfcommon.expand_includes(g7, reader)
_fused_bytes = len(json.dumps(_exp7).encode())
wfcommon.INCLUDE_BYTES_MAX = _fused_bytes - 1
try:
    refuses("fused-bytes recheck AFTER parent-ref rewrite refuses (pre-rewrite "
            "candidate alone is not enough)",
            g7, reader, "after the parent-reference rewrite")
finally:
    wfcommon.INCLUDE_BYTES_MAX = saved_b
# and the same graph fits at the default cap (the refuse above is the cap, not a bug)
_exp7b, _n7b = wfcommon.expand_includes(g7, reader)
check("export-name recheck graph expands cleanly at the default cap",
      len(_exp7b["nodes"]) == 5
      and byids(_exp7b)["tail"]["after"] == ["rev__approve", "rev__seat"],
      json.dumps(_exp7b["nodes"]))

# ---------------- (4b) include:null / present-but-not-list refuses (stripping
# is the storage contract: the passthrough branch must never keep the key) ------
refuses("include: null refused (present-but-not-list, not treated as absent)",
        {"name": "m", "include": None, "nodes": [agent("p")]}, reader, "non-empty list")
refuses("include: string refused",
        {"name": "m", "include": "review", "nodes": [agent("p")]}, reader, "non-empty list")
# absent key still passes through byte-identical (golden-solo pin above covers this)
_expnull, _ = wfcommon.expand_includes({"name": "p2", "nodes": [agent("q")]}, reader)
check("absent-include passthrough carries no include key", "include" not in _expnull)

# ---------------- (4c) alias grammar must stay a subset of the when-token head
# grammar: hyphenated alias + child when-gate used to fail OPEN (when rewrite
# silently no-op) — now a NAMED include-guard refusal at declaration ----------
refuses("hyphenated alias refused at the include guard (named, not a when error)",
        {"name": "m", "include": [{"as": "my-rev", "use": "review"}], "nodes": []},
        reader, "invalid alias", "my-rev")
refuses("hyphenated alias refused even WITHOUT a child when-gate (grammar is grammar)",
        {"name": "m", "include": [{"as": "a-", "use": "review"}], "nodes": []},
        reader, "invalid alias")
# underscore alias + child when-gate: the rewrite works and heads stay checkable
LIB["whengate"] = {"name": "whengate", "nodes": [
    agent("kick"), gate("g", after=["kick"], when="out.kick.done == True")]}
_exp7c, _n7c = wfcommon.expand_includes(
    {"name": "m", "include": [{"as": "my_rev", "use": "whengate"}], "nodes": []}, reader)
check("underscore alias with child when-gate rewrites cleanly",
      byids(_exp7c)["my_rev__g"]["when"] == "out.my_rev__kick.done == True",
      byids(_exp7c)["my_rev__g"]["when"])
check("token lexing sees the full namespaced head (no silent no-op)",
      wfcommon._include_when_heads(byids(_exp7c)["my_rev__g"]["when"])
      == ["my_rev__kick"])

# ---------------- (4d) child model_policy survives composition (C1: silent drop
# made it a fail-OPEN safety hole — a shelved forbidden-model floor must not
# dissolve because the graph got included) -------------------------------------
LIB["pol"] = {"name": "pol",
              "model_policy": {"forbidden_models": ["bad-b", "bad-a", "shared-x"]},
              "description": "child-only text",
              "nodes": [agent("pk")]}
g_pol = {"name": "m",
         "model_policy": {"forbidden_models": ["parent-x", "shared-x"]},
         "include": [{"as": "p", "use": "pol"}], "nodes": [agent("q")]}
expp, notesp = wfcommon.expand_includes(g_pol, reader)
check("child forbidden_models UNION into parent, deterministic sorted order",
      expp["model_policy"]["forbidden_models"]
      == sorted(["bad-a", "bad-b", "shared-x", "parent-x"]),
      expp.get("model_policy"))
check("merge emits an include_note naming the alias",
      any(n.startswith("p:") and "model_policy.forbidden_models merged into parent" in n
          for n in notesp), notesp)
# require_model is a floor too: child True ORs into the composite + notes loudly
LIB["req"] = {"name": "req", "model_policy": {"require_model": True},
              "nodes": [agent("rk", model="m1")]}
exprq, notesq = wfcommon.expand_includes(
    {"name": "m", "include": [{"as": "r", "use": "req"}], "nodes": [agent("q")]}, reader)
check("child require_model=True propagates into fused model_policy",
      exprq.get("model_policy", {}).get("require_model") is True, exprq.get("model_policy"))
check("require_model propagation emits a loud include_note",
      any("require_model" in n and n.startswith("r:") for n in notesq), notesq)
# a child require_model=False never relaxes a parent's True
LIB["reqno"] = {"name": "reqno", "model_policy": {"require_model": False},
                "nodes": [agent("rk")]}
exprn, _ = wfcommon.expand_includes(
    {"name": "m", "model_policy": {"require_model": True},
     "include": [{"as": "r", "use": "reqno"}], "nodes": [agent("q")]}, reader)
check("child require_model=False cannot relax parent's True",
      exprn["model_policy"]["require_model"] is True, exprn.get("model_policy"))
# parent with NO policy: the key is created from the child floor alone
expp2, _ = wfcommon.expand_includes(
    {"name": "m", "include": [{"as": "p", "use": "pol"}], "nodes": [agent("q")]}, reader)
check("policy-less parent gains the child floor",
      expp2["model_policy"]["forbidden_models"] == ["bad-a", "bad-b", "shared-x"],
      expp2.get("model_policy"))
# ONLY model_policy crosses the boundary: child description/defaults never ride
check("no other child top-level key is carried (description stays child-local)",
      "description" not in expp2 and "description" not in expp, sorted(expp2))
# nested: inner policy rides up transitively through a composite child
LIB["comp"] = {"name": "comp", "include": [{"as": "p", "use": "pol"}],
               "model_policy": {"forbidden_models": ["comp-x"]}, "nodes": [agent("c")]}
expp3, notes3 = wfcommon.expand_includes(
    {"name": "m", "include": [{"as": "c", "use": "comp"}], "nodes": []}, reader)
check("nested child policies union transitively",
      expp3["model_policy"]["forbidden_models"]
      == ["bad-a", "bad-b", "comp-x", "shared-x"], expp3.get("model_policy"))
# malformed child policy is a named refusal, never a silent drop or a crash.
# PR#84 review F-2: the shelf now goes through validate_graph_full, so an unknown
# policy key is refused by the standalone-validation pass itself (shared rules
# with direct submission) before the fuse-step policy check is ever reached.
LIB["polbad"] = {"name": "polbad", "model_policy": {"nope": 1}, "nodes": [agent("k")]}
refuses("child model_policy with unknown keys refused (named, via full standalone validation)",
        {"name": "m", "include": [{"as": "pb", "use": "polbad"}], "nodes": []},
        reader, "unknown policy key")
LIB["polbad2"] = {"name": "polbad2", "model_policy": {"forbidden_models": "x"},
                  "nodes": [agent("k")]}
refuses("child forbidden_models non-list refused",
        {"name": "m", "include": [{"as": "pb", "use": "polbad2"}], "nodes": []},
        reader, "forbidden_models")


# ---------------- (5) exports vs literal alias__id; bare-inner refuse ----------------
g5 = {"name": "m",
      "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"},
                   "exports": {"approve": "ship_gate"}}],
      "nodes": [agent("tail", after=["ship_gate"], inputs=["ship_gate.answer"]),
                # #68 ancestry: the `when` head must be a direct after-parent of the
                # gate once exports rewrites it (ship_gate -> rev__approve), so the
                # mapped ref rides the after list alongside the subtree entry point.
                gate("cond", after=["rev__kick", "rev__approve"],
                     when="out.ship_gate.ok == True")]}
exp5, _ = wfcommon.expand_includes(g5, reader)
n5 = byids(exp5)
check(n5["tail"]["after"] == ["rev__approve"]
      and n5["tail"]["inputs"] == ["rev__approve.answer"],
      "exported public name rewritten to namespaced id at after+inputs sites")
check(n5["cond"]["when"] == "out.rev__approve.ok == True",
      "exported name rewritten in when too", n5["cond"]["when"])
check(wfcommon.validate_graph_errors(exp5) == [],
      "exports-mapped graph validates", wfcommon.validate_graph_errors(exp5))
# exports naming a non-existent inner id -> refuse
refuses("exports naming a missing inner id refuses",
        {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"},
                                   "exports": {"ghost": "pub"}}], "nodes": []},
        reader, "exports", "ghost")
# exports public name shadowing a parent id -> refuse
refuses("exports shadowing a parent id refuses",
        {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"},
                                   "exports": {"approve": "tail"}}],
         "nodes": [agent("tail")]}, reader, "shadows")
# parent bare-inner ref -> REFUSE (all five surfaces)
for site, kw in [("after", {"after": ["kick"]}),
                 ("inputs", {"after": ["rev__kick"], "inputs": ["kick.items"]}),
                 ("requires", {"after": ["rev__kick"], "requires": {"kick": ["s"]}}),
                 ("fanout", {"after": ["kick"], "fanout": {"items_from": "kick.items"}})]:
    refuses(f"parent bare inner id in {site} refuses",
            {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"}}],
             "nodes": [agent("p", **kw)]}, reader, "bare inner id", "kick")
refuses("parent bare inner id in when refuses",
        {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"}}],
         "nodes": [gate("p", after=["rev__kick"], when="out.kick.ok")]},
        reader, "bare inner id")
# bare alias as an id -> refuse (alias is not a node)
refuses("parent after naming the bare alias refuses",
        {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"}}],
         "nodes": [agent("p", after=["rev"])]}, reader, "rev")
# dangling alias__id -> refuse with guidance even though literal form
refuses("parent after naming alias__ghost refuses",
        {"name": "m", "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"}}],
         "nodes": [agent("p", after=["rev__ghost"])]}, reader, "no such node")
# parent fanout consuming an included producer: items_from+after lockstep rewritten
g5b = {"name": "m",
       "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"},
                    "exports": {"kick": "kick_src"}}],
       "nodes": [agent("feeder", after=["kick_src"],
                       fanout={"items_from": "kick_src.items", "goal": "item"})]}
exp5b, _ = wfcommon.expand_includes(g5b, reader)
n5b = byids(exp5b)["feeder"]
check(n5b["after"] == ["rev__kick"] and n5b["fanout"]["items_from"] == "rev__kick.items",
      "parent items_from + after rewritten in lockstep via exports")
check(wfcommon.validate_graph_errors(exp5b) == [],
      "parent-side lockstep passes the validator's :914 direct-parent law")


# ---------------- (6) seed scoping ----------------
g6 = {"name": "m",
      "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/bound"}}],
      "nodes": [agent("pp", goal="parent wants {run.other}")]}   # disjoint key in parent
exp6, _ = wfcommon.expand_includes(g6, reader)
n6 = byids(exp6)
check(n6["rev__seat"]["context"] == "review /bound"
      and n6["rev__fan"]["fanout"]["goal"] == "check /bound",
      "include seeds render inside the subtree (goal/context/fanout.goal)")
check(n6["pp"]["goal"] == "parent wants {run.other}",
      "parent {run.X} text is NOT consumed by child seeds (scope = subtree only)")
# the door's own graph-level {run.X} (parent refs) stay for _bind_run_context untouched


# ---------------- (7) shared fixed-scratch-path notes ----------------
LIB["scratchy"] = {"name": "scratchy",
                   "nodes": [agent("w", goal="operate in /home/me/fixed/scratch dir")]}
g7 = {"name": "m",
      "include": [{"as": "s1", "use": "scratchy"},
                  {"as": "s2", "use": "scratchy"}],
      "nodes": [agent("p", goal="uses /home/me/fixed/scratch too")]}
exp7, notes7 = wfcommon.expand_includes(g7, reader)
check(any("s1" in n_ and "fixed path /home/me/fixed/scratch shared" in n_ for n_ in notes7),
      "child-vs-parent scratch collision warns, naming the alias", notes7)
check(any("s2" in n_ and "shared" in n_ for n_ in notes7),
      "child-vs-previously-included collision detected across includes", notes7)
check(byids(exp7)["s1__w"]["goal"] == byids(exp7)["s2__w"]["goal"]
      == "operate in /home/me/fixed/scratch dir",
      "scratch paths are NEVER rewritten (detect+warn only)")
# prose and URLs are not paths: no false-positive notes
LIB["prosy"] = {"name": "prosy",
                "nodes": [agent("w", goal="see notes/review.md at http://host/path, /a alone")]}
_, notes7b = wfcommon.expand_includes(
    {"name": "m", "include": [{"as": "p", "use": "prosy"}],
     "nodes": [agent("q", goal="notes/review.md and http://host/path")]} , reader)
check(notes7b == [], "relative/URL/single-segment text is not a fixed path", notes7b)


# ---------------- (8) efp stability ----------------
g8 = {"name": "m",
      "include": [{"as": "rev", "use": "review", "seeds": {"artifact": "/x"},
                   "exports": {"approve": "ship"}}],
      "nodes": [agent("iso", goal="untouched"),
                agent("wire", goal="downstream", after=["ship"])]}
exp8, _ = wfcommon.expand_includes(g8, reader)
old, new = byids(g8), byids(exp8)
check(wfcommon.def_hash(old["iso"]) == wfcommon.def_hash(new["iso"]),
      "untouched parent node: def_hash byte-identical after expansion")
check(wfcommon.efp(old, old["iso"]) == wfcommon.efp(new, new["iso"]),
      "untouched parent node: efp unchanged (replay-skip holds)")
check(wfcommon.def_hash(old["wire"]) != wfcommon.def_hash(new["wire"])
      and new["wire"]["after"] == ["rev__approve"],
      "rewired parent node: def_hash moves (intended re-run granularity)")
check(wfcommon.efp(new, new["rev__approve"]) !=
      wfcommon.efp({n["id"]: n for n in REVIEW["nodes"]},
                   {"id": "approve", "type": "gate", "question": "q approve",
                    "after": ["seat"], "when": "out.seat.ok == True and out.kick.done"})
      is not None,
      "included node has a (namespaced) fingerprint of its own — no crash")
# determinism: two expansions of the same author graph fingerprint identically
e1, _ = wfcommon.expand_includes(g8, reader)
e2, _ = wfcommon.expand_includes(copy.deepcopy(g8), reader)
check(wfcommon.graph_fingerprint(e1) == wfcommon.graph_fingerprint(e2)
      and wfcommon.graph_fingerprint(e1) is not None,
      "expansion is deterministic: same graph_fingerprint across launches")


# ---------------- include_provenance ----------------
prov = wfcommon.include_provenance(g8, reader)
check(prov == [{"alias": "rev", "name": "review",
                "source_digest": wfcommon.source_digest(REVIEW)}],
      "provenance stamps alias/name/source_digest in declaration order", prov)
check(wfcommon.include_provenance(plain, reader) == [],
      "no includes -> empty provenance")
prov3 = wfcommon.include_provenance(
    {"name": "m", "include": [{"as": "a", "use": "a"}], "nodes": []}, reader)
check([p["alias"] for p in prov3] == ["a", "a__b", "a__b__c"]
      and all(p["source_digest"] for p in prov3),
      "nested provenance walks inner-first, aliased outer__inner", prov3)
try:
    wfcommon.include_provenance({"name": "m", "include": [{"as": "z", "use": "gone"}],
                                 "nodes": []}, reader)
    check(False, "provenance refuses unknown entries honestly")
except ValueError as e:
    check("gone" in str(e), "provenance refuses unknown entries honestly", str(e))


# ---------------- API contract with the door wiring ----------------
res = wfcommon.expand_includes(g8, reader)
check(isinstance(res, tuple) and len(res) == 2
      and isinstance(res[0], dict) and isinstance(res[1], list),
      "contract: (dict, list) return shape")
check(isinstance(wfcommon.include_provenance(g8, reader), list),
      "contract: include_provenance returns a list")
for bad, needle in [({"nodes": []}, "graph must be an object"),
                    ]:
    try:
        wfcommon.expand_includes("[1,2]", reader)
        check(False, "non-dict graph raises ValueError")
    except ValueError as e:
        check("object" in str(e), "non-dict graph raises ValueError", str(e))
try:
    wfcommon.expand_includes({"nodes": []}, None)
    check(False, "non-callable reader raises ValueError")
except ValueError as e:
    check("callable" in str(e), "non-callable reader raises ValueError", str(e))


print(f"\n{'ALL PASS' if not fails else 'FAILURES'} ({ok} checks, {fails} failures)")
sys.exit(1 if fails else 0)
