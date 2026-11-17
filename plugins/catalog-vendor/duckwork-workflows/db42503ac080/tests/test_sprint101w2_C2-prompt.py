"""Sprint101 lane C2-prompt:
#9  JSON contract derived from the node schema — when a node has `schema`, the
    runner appends "Reply with ONLY a fenced ```json block whose keys are: <required>
    (types: ...)" to the child prompt (absent when no schema). On parse failure of
    the child's answer, extract the LAST balanced {...} object from stdout (strip
    fences, tolerate prose around it) before declaring schema/no_json failure.
#10 UPSTREAM AUTO-INJECT — every agent node with `after:` gets its DIRECT parents'
    committed outputs under '## Inputs' automatically; `inputs:` stays the way to
    pick a dotted path / non-parent ancestor; a parent listed in both appears once;
    per-parent cap 8 KB with a visible truncation marker; fan-out parents inject
    the merged item outputs like `inputs:` does.
Style: plain asserts, PASS/FAIL lines, exit 0/1 (test_door.py / test_inputs_0923.py).
"""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
home = HERE / "home_c2"
if home.exists():
    shutil.rmtree(home)
home.mkdir()
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

fake = str(HERE / "fake")

def run_graph(name, graph, seed=None, env_extra=None):
    runs = home / "workflows"; runs.mkdir(exist_ok=True)
    run = runs / name
    shutil.rmtree(run, ignore_errors=True)
    (run / "nodes").mkdir(parents=True); (run / "gates").mkdir()
    (run / "graph.json").write_text(json.dumps(graph))
    (run / "run.json").write_text(json.dumps({"name": name, "duckwork_bin": fake,
                                              "concurrency": 4, "node_timeout": 30,
                                              "started": "2099-01-01T00:00:00+00:00"}))
    for nid, rec in (seed or {}).items():
        byid = {n["id"]: n for n in graph["nodes"]}
        (run / "nodes" / f"{nid}.json").write_text(
            json.dumps({**rec, "efp": wfcommon.efp(byid, byid[nid]), "fp_rule_version": wfcommon.FP_RULE_VERSION}))
    plog = home / f"{name}.prompts.log"
    if plog.exists():
        plog.unlink()
    env = {**os.environ, "DUCKWORK_HOME": str(home), "WF_RUNS_ROOT": str(runs),
           "FAKE_LOG": str(home / f"{name}.fake.log"),
           "FAKE_PROMPT_LOG": str(plog)}
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", name],
                       capture_output=True, text=True, timeout=120, env=env)
    prompts = plog.read_text().split("\n=====PROMPT=====\n")[1:] if plog.exists() else []
    return run, prompts, p.stdout + p.stderr

# ============ #9a: derived contract line present/absent ============
sch = {"type": "object", "required": ["verdict", "score"],
       "properties": {"verdict": {"type": "string"}, "score": {"type": "number"}}}
run, prompts, out = run_graph("20990101-100001-schema",
    {"name": "s", "nodes": [{"id": "x", "type": "agent", "goal": "SCHEMA-NODE", "schema": sch}]})
pr = prompts[0]
check("#9 contract line present when schema set",
      "Reply with ONLY a fenced ```json block whose keys are: verdict, score (types: verdict=string, score=number)" in pr,
      pr[-400:])
check("#9 contract line lands before the generic CONTRACT",
      pr.find("whose keys are:") < pr.find("Finish your answer with ONE"))

run, prompts, out = run_graph("20990101-100002-noschema",
    {"name": "n", "nodes": [{"id": "x", "type": "agent", "goal": "PLAIN-NODE"}]})
pr = prompts[0]
check("#9 contract line absent when no schema", "whose keys are:" not in pr, pr[-300:])
check("#9 generic CONTRACT still present without schema", "Finish your answer with ONE" in pr)

# ============ #9b: last-balanced-object extraction (unit) ============
spec = importlib.util.spec_from_file_location("hwf_c2", BUILD / "wf.py")
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

p1, e1 = W.extract_json('Some prose before {"verdict": "ship"} more prose after.')
check("#9 prose before + after, bare object extracted", p1 == {"verdict": "ship"} and e1 is None, f"{p1} {e1}")

p2, _ = W.extract_json('first {"a": 1} then {"b": 2} tail')
check("#9 two objects -> LAST one wins", p2 == {"b": 2}, p2)

p3, _ = W.extract_json("noise\n```json\n{broken,,\n```\nbut here is my real answer:\n{\"k\": \"v\"}\ndone")
check("#9 broken fence + valid trailing object -> object extracted (not result-fallback)",
      p3 == {"k": "v"}, p3)

p4, _ = W.extract_json('prose {not json at all} tail {"ok": true}')
check("#9 invalid candidate skipped, later valid one extracted", p4 == {"ok": True}, p4)

p5, _ = W.extract_json('answer: {"s": "has { brace } inside"} end')
check("#9 braces inside strings don't confuse the scanner", p5 == {"s": "has { brace } inside"}, p5)

p6, e6 = W.extract_json('truly no braces here at all')
check("#9 no object anywhere -> unchanged {result} fallback",
      p6 == {"result": "truly no braces here at all"} and e6 is None, f"{p6} {e6}")

p7, e7 = W.extract_json("")
check("#9 empty stdout -> unchanged (None, err)", p7 is None and e7 == "no json fence found", f"{p7} {e7}")

p8, _ = W.extract_json('{"outer": {"inner": 1}} trailing}')
check("#9 nested object extracted; stray trailing brace tolerated",
      p8 == {"outer": {"inner": 1}}, p8)

# ============ #9c: end-to-end — noisy child whose fenced answer is prose ============
NOISY = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
run, prompts, out = run_graph("20990101-100003-noisy",
    {"name": "noisy", "nodes": [{"id": "a", "type": "agent", "goal": "NOISY_JSON", "schema": NOISY}]},
    env_extra={"FAKE_MODE": "noisy"})
rec = json.loads((run / "nodes" / "a.json").read_text())
check("#9 noisy stdout (prose before/after, two objects) commits the LAST object, done on first pass",
      rec["status"] == "done" and rec["output"] == {"ok": True, "attempt": 2} and rec.get("spawn") == 0,
      json.dumps(rec)[:200])

# ============ #10a: direct parents auto-injected without `inputs:` ============
run, prompts, out = run_graph("20990101-100004-auto",
    {"name": "auto", "nodes": [
        {"id": "gen", "type": "agent", "goal": "LIST:"},
        {"id": "use", "type": "agent", "after": ["gen"], "goal": "AUTOUSE"}]})
pr = prompts[1]
check("#10 direct parent injected with no inputs: field",
      "## Inputs" in pr and "\ngen\n```json\n" in pr, pr[:200])
check("#10 injected parent block carries the committed output",
      json.loads(pr.split("\ngen\n```json\n")[1].split("\n```")[0]) == {"result": ["a", "b", "c"]},
      pr[:300])
check("#10 ## Inputs still lands before the output contract",
      pr.find("## Inputs") < pr.find("Finish your answer"))

# ============ #10b: no duplicate when the parent is also in inputs: ============
run, prompts, out = run_graph("20990101-100005-dup",
    {"name": "dup", "nodes": [
        {"id": "gen", "type": "agent", "goal": "LIST:"},
        {"id": "use", "type": "agent", "after": ["gen"], "goal": "DUPUSE", "inputs": ["gen.result.1"]}]})
pr = prompts[1]
check("#10 parent covered by a dotted inputs: ref appears exactly once",
      pr.count("```json") == 2 and pr.count('"b"') >= 1
      and "\ngen\n```json\n" not in pr and "\ngen.result.1\n```json\n" in pr,
      pr[pr.find("## Inputs"):pr.find("## Inputs") + 200])

# ============ #10c: 8 KB cap with visible marker ============
g = {"name": "cap", "nodes": [
     {"id": "big", "type": "agent", "goal": "unused (seeded)"},
     {"id": "down", "type": "agent", "after": ["big"], "goal": "CAPHOP"}]}
run, prompts, out = run_graph("20990101-100006-cap", g,
                              seed={"big": {"status": "done", "output": {"blob": "y" * 20000}}})
pr = prompts[0]
full = len(json.dumps({"blob": "y" * 20000}, ensure_ascii=False, indent=2, default=str))
check("#10 auto-injected parent capped at 8000 chars with exact marker",
      f"…[truncated {full - 8000} chars; full record at nodes/big.json]" in pr, pr[-200:])
check("#10 capped block actually truncated", 7000 < pr.count("y") < 20000, pr.count("y"))

# ============ #10d: fan-out parent injects the merged items ============
run, prompts, out = run_graph("20990101-100007-fo",
    {"name": "fo", "nodes": [
        {"id": "gen", "type": "agent", "goal": "LIST:"},
        {"id": "fan", "type": "agent", "after": ["gen"],
         "fanout": {"items": ["p", "q"], "goal": "FO {item}"}},
        {"id": "join", "type": "agent", "after": ["fan"], "goal": "JOIN"}]})
join_pr = [p for p in prompts if p.startswith("JOIN")][0]
sec = join_pr.split("## Inputs")[1].split("Finish your answer")[0]
check("#10 fan-out parent injects merged item outputs the same way inputs: does",
      "\nfan\n```json\n" in sec and '"items"' in sec, sec[:300])
check("#10 fan-out parent injected exactly once", sec.count("```json") == 1, sec[:200])

# ============ #10e: two parents -> both injected, once each ============
run, prompts, out = run_graph("20990101-100008-two",
    {"name": "two", "nodes": [
        {"id": "a1", "type": "agent", "goal": "P1"},
        {"id": "a2", "type": "agent", "goal": "P2"},
        {"id": "b", "type": "agent", "after": ["a1", "a2"], "goal": "MERGE"}]})
pr = prompts[-1]
sec = pr.split("## Inputs")[1].split("Finish your answer")[0]
check("#10 both direct parents injected once each",
      sec.count("```json") == 2 and "\na1\n```json\n" in sec and "\na2\n```json\n" in sec,
      sec[:250])

print("\nALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
