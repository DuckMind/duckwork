#!/usr/bin/env python3
"""Library verbs + /wf command: save (from run_id / inline), library list, run from=<name>,
name validation, /wf list + replay instruction. Hermetic (fake launcher, sandboxed HOME)."""
import json, os, shutil, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home6"
os.environ["DUCKWORK_HOME"] = str(HOME)
# #71 (r5-corrected): DUCKWORK_HOME alone does NOT sandbox the shelf — a lane process
# carries the context-local home override which outranks the env, so runs_root()/
# library_root() resolve to the SHARED estate shelf. And WF_RUNS_ROOT only outranks
# the home-derived DEFAULT — it does NOT outrank an owner-configured
# plugins.entries.duckwork-workflows.settings.runs_root, which wins first (resolver
# precedence #42, owner design). That is why these tests pin BOTH: the env var AND,
# via wf_test_isolation.install below, the plugin's settings.runs_root to the
# identical scratch root. Set only one and these saves pollute production
# (shelf-is-live law).
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
shutil.rmtree(HOME, ignore_errors=True)
import importlib.util
spec = importlib.util.spec_from_file_location("hw", str(BUILD.parent / "__init__.py"))
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
FAKE = str(BUILD / "fake")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = FAKE
ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond
def call(**a): return json.loads(hw.handle(a))

G = {"name": "Lib Demo", "nodes": [
    {"id": "a", "type": "agent", "goal": "LIST: go"},
    {"id": "fan", "type": "agent", "after": ["a"], "fanout": {"items_from": "a.result", "goal": "item {item}"}},
    {"id": "g", "type": "gate", "after": ["fan"], "question": "ok?", "options": ["y", "n"]}]}

# L1 empty library
check("L1 library empty", call(action="library")["library"] == [])
check("L1b /wf on empty says so", "empty" in hw._wf_command(""))

# L2 save inline (name from graph, slugged), description kept
r = call(action="save", graph=G, name="lib-demo", description="demo graph")
check("L2 save inline", r.get("saved") == "lib-demo" and r.get("nodes") == 3, json.dumps(r))
lib = call(action="library")["library"]
check("L2b library lists it with counts", lib and lib[0]["name"] == "lib-demo" and lib[0]["gates"] == 1 and lib[0]["fanouts"] == 1
      and lib[0]["description"] == "demo graph", json.dumps(lib))

# L3 bad names rejected
check("L3 bad name rejected", "invalid library name" in json.dumps(call(action="save", graph=G, name="../evil")))
check("L3b run from unknown lists library", "no library graph" in json.dumps(call(action="run", **{"from": "nope"})))

# L4 run from=<name> actually runs (fake launcher) to the gate
r = call(action="run", **{"from": "lib-demo"})
rid = r.get("run_id"); check("L4 run from=lib-demo launches", bool(rid), json.dumps(r))
st = call(action="wait", run_id=rid, timeout=60)
check("L4b replay reaches the gate", st.get("status") == "held" and (st.get("gate") or {}).get("id") == "g", json.dumps({k: st.get(k) for k in ("status", "gate")}))
g = json.load(open(HOME / "workflows" / rid / "graph.json"))
check("L4c run's graph name = library stem", g.get("name") == "lib-demo")

# L5 save FROM a run (round-trip), overwrite semantics
r = call(action="save", run_id=rid, name="lib-demo-v2")
check("L5 save from run_id", r.get("saved") == "lib-demo-v2")
check("L5b library has two", len(call(action="library")["library"]) == 2)

# L6 /wf command text
t = hw._wf_command("")
check("L6 /wf lists both", "lib-demo" in t and "lib-demo-v2" in t and "/wf <name>" in t, t[:120])
t = hw._wf_command("lib-demo ship the colors")
check("L6b /wf <name> note -> atomic replay binding", 'from:"lib-demo"' in t and 'run_context:"ship the colors"' in t and "steer" not in t, t[:200])
check("L6c /wf unknown -> lists available", "Available: lib-demo" in hw._wf_command("zzz"))
check("L6d /wf bad name -> validation msg", "invalid library name" in hw._wf_command("../x"))

# L7 F-2 (#62) quarantine fixture — EXACT pair: valid good.json beside the
# malformed broken.json. Fail-closed on the entry (typed refusal), fail-open on
# the library (nothing crashes, the good entry stays fully usable).
import json as _json
good = {"name": "good", "nodes": [{"id": "e", "type": "echo", "output": 1}]}
broken = {"meta": {"description": "junk"}, "graph": {"nodes": ["oops"]}}
for stem, doc in (("good", good), ("broken", broken)):
    (Path(HOME) / "workflows" / "library" / (stem + ".json")).write_text(_json.dumps(doc))
out = call(action="library")
check("L7 library lists good beside broken, no crash",
      "good" in {x["name"] for x in out["library"]}
      and "broken" not in {x["name"] for x in out["library"]}, _json.dumps(out))
check("L7b broken is named with its typed refusal reason",
      any(q["name"] == "broken" and q["reason"] == "invalid: nodes[0] is not an object"
          for q in out.get("quarantined", [])), _json.dumps(out.get("quarantined")))
check("L7c run from=good works while broken sits there",
      bool(call(action="run", **{"from": "good"}).get("run_id")))
check("L7d run from=broken nudges, never crashes",
      "no library graph" in call(action="run", **{"from": "broken"}).get("error", ""))
check("L7e typo hint still works beside broken",
      "good" in call(action="run", **{"from": "good-typo"}).get("closest", []))
t = hw._wf_command("")
check("L7f /wf lists both rows; bad shows WHY it was refused",
      "good" in t and "broken" in t and "invalid: nodes[0] is not an object" in t, t[:200])
t = hw._wf_command("broken")
check("L7g /wf <bad> shows the refusal, not a crash",
      "refused: invalid: nodes[0] is not an object" in t, t[:160])
(Path(HOME) / "workflows" / "library" / "broken.json").unlink()
out = call(action="library")
check("L7h removing broken fully restores (no skip rows at all)",
      {x["name"] for x in out["library"]} >= {"good", "lib-demo", "lib-demo-v2"}
      and "skipped" not in out and "quarantined" not in out, _json.dumps(out)[:200])

call(action="stop", run_id=rid)

# ---- L8 faceted tags (#70) on the #50 envelope dialect ----
def entry(name):  # raw file content of a library entry
    return json.loads((HOME / "workflows" / "library" / f"{name}.json").read_text())

r = call(action="save", graph=G, name="tagged8", description="tagged demo",
         tags=["Use_Case:Code-Review", "use_case:code-review", "repo:sglang"])
check("L8 save normalizes+collapses into meta envelope",
      entry("tagged8")["meta"]["tags"] == ["use_case:code-review", "repo:sglang"], json.dumps(r))
check("L8b legacy flat token still valid", "saved" in call(
    action="save", graph=G, name="flat8", tags=["review"]))
check("L8c unknown facet lists facets", "allowed facets" in json.dumps(
    call(action="save", graph=G, name="t1", tags=["intent:x"])))
check("L8d bare facet rejected", "invalid tag" in json.dumps(
    call(action="save", graph=G, name="t1", tags=["risk:"])))
check("L8e double colon rejected (not silently flat)", "invalid tag" in json.dumps(
    call(action="save", graph=G, name="t1", tags=["use_case:a:b"])))
check("L8f 49-char tag rejected", "invalid tag" in json.dumps(
    call(action="save", graph=G, name="t1", tags=["note:" + "x" * 44])))
check("L8g tags:[] stays the #50 fail-closed error", "tags" in json.dumps(
    call(action="save", graph=G, name="tagged8", tags=[])))

# retain-on-overwrite: resave the SAME entry with no tags arg -> old tags ride
r = call(action="save", graph=G, name="tagged8", description="re-shelved")
check("L8h resave without tags RETAINS meta tags AND prior meta description",
      entry("tagged8")["meta"]["tags"] == ["use_case:code-review", "repo:sglang"]
      and entry("tagged8")["meta"]["description"] == "re-shelved", json.dumps(entry("tagged8")["meta"]))
call(action="save", graph=dict(G, description="bare desc"), name="bare8")
call(action="save", graph=G, name="bare8", tags=["use_case:research"])
check("L8i tagging a BARE entry carries its top-level description into meta",
      entry("bare8")["meta"]["tags"] == ["use_case:research"]
      and entry("bare8")["meta"]["description"] == "bare desc", json.dumps(entry("bare8").get("meta")))

# library: filter, vocab, self-diagnosis
call(action="save", graph=dict(G, name="D8"), name="d8", description="x",
     tags=["use_case:code-review", "domain:gpu"])
lib = call(action="library", tags=["use_case:code-review"])["library"]
check("L8j ALL-match filter returns tagged rows only",
      {x["name"] for x in lib} == {"tagged8", "d8"}, json.dumps([x["name"] for x in lib]))
lib = call(action="library", tags=["USE_CASE:CODE-REVIEW", "REPO:SGLANG"])["library"]
check("L8k mis-cased compound filter still matches",
      [x["name"] for x in lib] == ["tagged8"], json.dumps([x["name"] for x in lib]))
res = call(action="library", tags=["use_case:code-review", "repo:nope"])
check("L8l empty result self-diagnoses via match counts",
      res["library"] == [] and res["tag_match_counts"] == {"use_case:code-review": 2, "repo:nope": 0},
      json.dumps(res.get("tag_match_counts")))
vocab = call(action="library")["tag_vocab"]
check("L8m tag_vocab whole-library", vocab.get("use_case:code-review") == 2
      and vocab.get("review") == 1, json.dumps(vocab))  # legacy flat token counts too
check("L8n filter reuses the same law", "unknown facet" in json.dumps(call(action="library", tags=["task:x"])))

# a tagged envelope entry replays end to end
r = call(action="run", **{"from": "tagged8"})
rid2 = r.get("run_id"); check("L8o tagged envelope replays", bool(rid2), json.dumps(r))
g2 = json.load(open(HOME / "workflows" / rid2 / "graph.json"))
check("L8p replayed graph.json stays validator-clean (tags live in meta, not the graph)",
      "tags" not in g2 and g2.get("name") == "tagged8", json.dumps(list(g2)))
call(action="stop", run_id=rid2)

check("L8q /wf lists tags inline", "[use_case:code-review repo:sglang]" in hw._wf_command(""))
check("L8r unfiltered call on a tagged library carries the reuse-hint",
      "never coin unseen tags" not in call(action="library")["hint"]
      and "never coin unseen tags" in call(action="library", tags=["use_case:research"])["hint"])

# #146 item 3: erase-by-file-edit is a STATE, not a resurrection; garbage fails closed
call(action="save", graph=G, name="erase8", tags=["domain:net"], description="keep")
_ep = HOME / "workflows" / "library" / "erase8.json"
_e = json.loads(_ep.read_text()); _e["meta"]["tags"] = []; _ep.write_text(json.dumps(_e))
call(action="save", graph=G, name="erase8")   # plain resave over the deliberate erase
_e2 = json.loads(_ep.read_text())
check("L8s stored tags:[] is the erase state — resave keeps [] AND the envelope",
      _e2.get("meta", {}).get("tags") == [] and "graph" in _e2, json.dumps(_e2)[:200])
_e2["meta"]["tags"] = "notalist"; _ep.write_text(json.dumps(_e2))
r3 = call(action="save", graph=G, name="erase8")
check("L8t stored non-list meta.tags fails closed (repair-or-delete)",
      "error" in r3 and "not a list" in r3["error"], json.dumps(r3))
_e3 = json.loads(_ep.read_text())
check("L8u the refused resave left the file untouched", _e3["meta"]["tags"] == "notalist")

call(action="stop", run_id=rid)
print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
