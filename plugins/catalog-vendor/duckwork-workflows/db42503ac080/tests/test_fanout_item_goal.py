#!/usr/bin/env python3
"""fb12da4 — fan-out own-goal collision guard (WARN-ONLY, no fail-closed).

Mechanism (mid-flight amend probe, reproduced on an unpatched engine): an item's own `goal` wins
over the fan-out template at the own-goal override in `one()`. A graph whose
per-item `goal` fields all carry another item's already-substituted text (the
waveA2/A3 amend shape) shipped that item's lane token to EVERY other child on
the respawned wave — proven: collision=True against the unpatched engine.

The guard, per the owner ruling: scoped to fields the fan-out template itself
declares via {item.FIELD}; an own-goal that bakes a sibling's value for a
declared field gets a loud `item.goal_drift` event and the template render is
preferred. NEVER fail-closed — there is no 'goal_mismatch' spawn-refusal
anywhere; an item whose own-goal looks collided but matches no sibling still
spawns with its verbatim own text. Graphs whose items own the payload verbatim
(template '{item.goal}', the waveA3/A4 author pattern — no declared
{item.FIELD}) never enter the path.

Second guard, same event vocabulary: a rendered goal still carrying a
placeholder that resolves to nothing — dotted '{item.X}' (fmt_goal only
interpolates bare {FIELD}) or a bare {X} naming no item key — gets a loud
one-line 'template placeholder {item.X} names no item field' warning
(`item.goal_dangling`). The 00:47:53 amend's dotted {item.lane} rewrite landed
on every wave-2 child as literal text; this makes that authoring hazard
self-diagnosing. Warn, never fail.

Runnable two ways (repo convention): `python3 tests/test_fanout_item_goal.py`
prints PASS/FAIL lines, exit 0 = green; pytest can also collect the test_*
functions directly.
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
HOME  = BUILD / "home-goal"
RUNS  = HOME / "workflows"
FAKE  = str(BUILD / "fake")
N = 8

sys.path.insert(0, str(ROOT))
import wf as _wf

def lane(i): return f"lane-{i:02}TOKEN"
def cards(i): return f"cards-{i:02}"

def clean_items():
    return [{"lane": lane(i), "cards": cards(i),
             "goal": f"PROCESS item {i}: report {lane(i)} {cards(i)} SLEEP 0.2 reply"}
            for i in range(N)]

def corrupt_items():
    # waveA2/A3 amend shape (exactly the probe's baked text, SLEEP included so
    # every item — rescued or not — gets its fake child's turn, never tripping
    # the pre-first-message liveness kill): template kept, every item.goal =
    # item[4]'s fully-substituted text, identical across all items.
    baked = f"PROCESS item 4: report {lane(4)} {cards(4)} SLEEP 0.2 reply"
    its = clean_items()
    for it in its:
        it["goal"] = baked
    return its

def fan_graph(items, tmpl="Act on {item.lane} [{index}] cards={item.cards} reply"):
    return {"name": "fb12da4-goal", "nodes": [{"id": "fan", "type": "agent",
            "fanout": {"items": items, "goal": tmpl,
                       "schema": {"type": "object", "required": ["result"],
                                  "properties": {"result": {"type": "string"}}}},
            "timeout": 30}]}

def fan_graph_bare(items):
    # grammar-canonical bare {FIELD} placeholders (fmt_goal's own syntax)
    return {"name": "fb12da4-goal", "nodes": [{"id": "fan", "type": "agent",
            "fanout": {"items": items, "goal": "Act on {lane} [{index}] cards={cards} reply",
                       "schema": {"type": "object", "required": ["result"],
                                  "properties": {"result": {"type": "string"}}}},
            "timeout": 30}]}

def verbatim_graph(items):
    # legitimate own-goal author pattern (waveA4/A3): template '{item.goal}' —
    # items own the payload; the guard must never touch it.
    return fan_graph(items, tmpl="{item.goal}")

env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake-goal.log"),
           PYTHONUNBUFFERED="1")

def mk(run_id, graph):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(graph))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "item_concurrency": 2}))
    return r

def wf(run_id, timeout=120):
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                       env=env, capture_output=True, text=True, timeout=timeout)
    return p.stdout.strip()

def spawn_prompts(r):
    return {p.name: p.read_text(encoding="utf-8") for p in sorted((r / "logs").glob("fan.*.a*.prompt.md"))}

def idx_of(name):
    return int(name.split(".")[1])

def _assert_no_fail_closed(r, label):
    # The owner ruling is absolute: warn-and-prefer-template ONLY. No
    # 'goal_mismatch' error_class may exist anywhere in the run — neither in
    # events nor in any committed item result.
    assert "goal_mismatch" not in (r / "events.jsonl").read_text(), \
        f"{label}: fail-closed goal_mismatch resurfaced in events"
    rec = json.loads((r / "nodes/fan.json").read_text())
    for row in rec.get("output", {}).get("all_results", []):
        assert row.get("error_class") != "goal_mismatch", \
            f"{label}: item result carries fail-closed goal_mismatch: {row}"

def _assert_prompts_carry_own(prompts, label):
    assert prompts, f"{label}: no spawn prompts were harvested"
    seen_idx = {idx_of(n) for n in prompts}
    assert seen_idx == set(range(N)), f"{label}: missing item prompts: {sorted(set(range(N)) - seen_idx)}"
    for name, text in prompts.items():
        i = idx_of(name)
        assert lane(i) in text, f"{label}: {name} lacks its own lane token {lane(i)}"
        assert cards(i) in text, f"{label}: {name} lacks its own cards token {cards(i)}"
        for k in range(N):
            if k != i:
                assert lane(k) not in text and cards(k) not in text, \
                    f"{label}: {name} (item {i}) carries foreign item {k} token"
    # explicit cross-item token-sharing assertion
    toks = {idx_of(n): {lane(idx_of(n)): lane(idx_of(n)), cards(idx_of(n)): cards(idx_of(n))}
            for n in prompts}
    for a in toks:
        for b in toks:
            if a < b:
                shared = set(toks[a]) & set(toks[b])
                assert not shared, f"{label}: items {a} and {b} share item-specific tokens {shared}"

def test_every_spawned_prompt_carries_own_item():
    """Corrupt amended graph (every item.goal = item[4]'s substituted text) +
    respawn: the guard rescues warn-only — each prompt must carry its OWN
    lane/cards, never another's, every rescued item emits item.goal_drift,
    the node still commits done, and no fail-closed class exists."""
    r = mk("fb12-goal-corrupt", fan_graph(corrupt_items()))
    # mid-flight amend shape, deterministic half: runner 1 starts the wave...
    p1 = subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run",
                           "fb12-goal-corrupt"], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, start_new_session=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        if len(spawn_prompts(r)) >= 2:
            break
        time.sleep(0.1)
    # ... the corrupt graph is what sits on disk (the amend landed); kill -9 the
    # runner and respawn (re-enter wf.py run) — wave re-renders from the mutated
    # graph.json, exactly the post-amend respawn that collided in the probe.
    try: os.killpg(os.getpgid(p1.pid), 9)
    except Exception: pass
    p1.wait(timeout=30)
    out = wf("fb12-goal-corrupt")
    assert "WORKFLOW_DONE" in out, f"run did not finish: {out}"
    _assert_prompts_carry_own(spawn_prompts(r), "corrupt-amend")
    rec = json.loads((r / "nodes/fan.json").read_text())
    assert rec["status"] == "done", f"corrupted items must be SAVED by the guard, not failed: {rec.get('error')}"
    ev = (r / "events.jsonl").read_text()
    drifts = [json.loads(l) for l in ev.splitlines() if '"item.goal_drift"' in l]
    assert drifts, "guard must log a loud item.goal_drift event"
    assert all(d.get("warning") for d in drifts), "item.goal_drift must carry a loud warning"
    _assert_no_fail_closed(r, "corrupt-amend")

def test_clean_fanout_untouched():
    """No own-goal fields at all: plain template render, all done, no guard
    events of any kind."""
    items = [{"lane": lane(i), "cards": cards(i)} for i in range(N)]
    r = mk("fb12-goal-clean", fan_graph_bare(items))
    out = wf("fb12-goal-clean")
    assert "WORKFLOW_DONE" in out, out
    _assert_prompts_carry_own(spawn_prompts(r), "clean")
    ev = (r / "events.jsonl").read_text()
    assert "item.goal_drift" not in ev
    assert "item.goal_dangling" not in ev
    _assert_no_fail_closed(r, "clean")

def test_own_goal_passthrough_author_pattern_survives():
    """Template '{item.goal}' (items own the payload, waveA3/A4 author pattern):
    own-goal shipped VERBATIM including shared HARD-RULES-style foreign mentions,
    guard never fires."""
    items = clean_items()
    shared = "HARD RULE: never write outside your lane; see lane-00TOKEN for the exemplar."
    for it in items:
        it["goal"] = it["goal"] + " " + shared          # EVERY item names item 0's lane
    r = mk("fb12-goal-verbatim", verbatim_graph(items))
    out = wf("fb12-goal-verbatim")
    assert "WORKFLOW_DONE" in out, out
    prompts = spawn_prompts(r)
    for name, text in prompts.items():
        assert shared in text, f"verbatim own-goal payload was rewritten in {name}"
    ev = (r / "events.jsonl").read_text()
    assert "item.goal_drift" not in ev, \
        "guard fired on the {item.goal} pass-through pattern"
    assert "item.goal_dangling" not in ev, \
        "dangling warning fired on a fully-resolved {item.goal} render"
    _assert_no_fail_closed(r, "verbatim")

def test_orphan_baked_own_goal_spawns_warn_only():
    """The old fail-closed case, now warn-only: template declares
    {item.lane}/{item.cards}; item 0's own-goal bakes a value belonging to NO
    current item (the residue of an amend that dropped the original — no drift
    match). The brief forbids strand-on-suspicion: item 0 must STILL SPAWN with
    its verbatim own text (prompt artifact exists), and no goal_mismatch class
    may exist anywhere. The healthy item 1 runs normally."""
    items = [{"lane": lane(0), "cards": cards(0),
              "goal": f"PROCESS lane-99TOKEN cards-99 SLEEP 0.2 reply"},   # orphaned baked text
             {"lane": lane(1), "cards": cards(1),
              "goal": f"PROCESS {lane(1)} {cards(1)} SLEEP 0.2 reply"}]     # healthy item
    r = mk("fb12-goal-orphan", fan_graph(items))
    out = wf("fb12-goal-orphan")
    assert "WORKFLOW_DONE" in out, out
    rec = json.loads((r / "nodes/fan.json").read_text())
    assert rec["status"] == "done", f"orphan shape must never strand the node: {rec.get('error')}"
    allr = {x["item"]["cards"]: x for x in rec["output"]["all_results"]}
    assert allr[cards(0)]["status"] == "done", \
        f"warn-only: the orphan item must still spawn and finish, got {allr[cards(0)]}"
    assert allr[cards(1)]["status"] == "done", \
        f"the healthy item must still run, got {allr[cards(1)]}"
    assert (r / "logs/fan.0.a0.prompt.md").exists(), \
        "warn-only: the orphan item must SPAWN (its verbatim own text reaches the child)"
    assert "lane-99TOKEN" in (r / "logs/fan.0.a0.prompt.md").read_text(), \
        "no-drift own-goal must reach the child VERBATIM (no silent rewrite)"
    _assert_no_fail_closed(r, "orphan")

def test_dangling_placeholder_warns_at_spawn():
    """The section-census wave-2 shape: the template declares dotted
    {item.lane} which fmt_goal NEVER interpolates — every child used to receive
    the literal silently. Now: the literal still reaches the child (documented
    fmt_goal contract, no engine substitution change) BUT every spawn emits a
    loud one-line 'template placeholder {item.X} names no item field' warning,
    and the run still finishes warn-only."""
    items = [{"lane": lane(i), "cards": cards(i)} for i in range(4)]
    tmpl = "Act on {item.lane} [{index}] reply. Report done as {\"result\": \"ok\"}."
    r = mk("fb12-goal-dangling", fan_graph(items, tmpl=tmpl))
    out = wf("fb12-goal-dangling")
    assert "WORKFLOW_DONE" in out, f"warn-only must never block the run: {out}"
    rec = json.loads((r / "nodes/fan.json").read_text())
    assert rec["status"] == "done", f"dangling placeholders must never strand the node: {rec.get('error')}"
    prompts = spawn_prompts(r)
    assert prompts, "dangling-warning items must still spawn"
    for name, text in prompts.items():
        assert "{item.lane}" in text, \
            f"{name}: dangling placeholder must ship verbatim (no silent rewrite)"
        assert lane(idx_of(name)) not in text            # the literal was never a value
    ev = (r / "events.jsonl").read_text()
    dangles = [json.loads(l) for l in ev.splitlines() if '"item.goal_dangling"' in l]
    assert dangles, "a dangling {item.lane} template must warn at every spawn"
    assert all(d.get("warning") ==
               f"template placeholder {d['placeholder']} names no item field"
               for d in dangles), "the warning must be the loud one-line form"
    assert any(d["placeholder"] == "{item.lane}" for d in dangles), \
        f"expected the literal {{item.lane}} placeholder to be named, got {dangles}"
    _assert_no_fail_closed(r, "dangling")

def test_dangling_helper_scoping():
    """Unit-lock of _dangling_placeholders (mirrors fmt_goal's lookup):
    resolved tokens and prose braces are silent; field-like tokens warn."""
    item = {"lane": "L", "cards": "C"}
    assert _wf._dangling_placeholders("plain goal, no braces", item) == []
    assert _wf._dangling_placeholders("", item) == []
    # fmt_goal resolves bare {FIELD}, {item}, {index}
    assert _wf._dangling_placeholders("go {lane} {cards} {index} {item}", item) == []
    # fmt_goal NEVER resolves dotted spellings -> every one is dangling
    assert _wf._dangling_placeholders("go {item.lane} and {item.cards}", item) == \
        ["{item.lane}", "{item.cards}"]
    assert _wf._dangling_placeholders("{item.index}", item) == ["{item.index}"]
    # bare token naming no item key
    assert _wf._dangling_placeholders("go {lanex} {lane}", item) == ["{lanex}"]
    # prose braces that cannot name a field: never warned
    assert _wf._dangling_placeholders("Return {ok, findings} then {a: 1}", item) == []
    # de-duplicated, order-preserving
    assert _wf._dangling_placeholders("{item.lane} {item.lane}", item) == ["{item.lane}"]

if __name__ == "__main__":
    ok = True
    (BUILD / "fake-goal.log").write_text("")
    for fn in (test_every_spawned_prompt_carries_own_item,
               test_clean_fanout_untouched,
               test_own_goal_passthrough_author_pattern_survives,
               test_orphan_baked_own_goal_spawns_warn_only,
               test_dangling_placeholder_warns_at_spawn,
               test_dangling_helper_scoping):
        try:
            fn()
            print("PASS " + fn.__name__)
        except Exception as e:
            ok = False
            print("FAIL " + fn.__name__ + "  " + repr(e)[:400])
    print("ALL PASS" if ok else "FAILURES")
    sys.exit(0 if ok else 1)
