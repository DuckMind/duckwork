#!/usr/bin/env python3
"""fb-validator-duo (2026-09-26): the validator-cap duo + the manifest-clip pin.

Row 2 (plugin fix):
 1. node max_turns=240 -> the rejection names BOTH '240' and the cap '200'
    (exact form: "max_turns 240 exceeds cap 200 (must be a number in (0, 200])").
 2. node timeout and run_budget rejections have the same shape (value AND cap).
 3. defaults.max_turns / defaults.timeout rejections have the same shape.
 4. the '(must be a number in (0, {hi}])' parenthetical survives (substring-
    matchers on the old wording keep working).
 5. __init__.py act_wait KEEPS the min() clamp and echoes
    'timeout clamped to 1800s (requested X)' when the clamp bites; a request
    <= 1800 carries no timeout_note.

Row 1 (pin-test only — NO plugin code fix): the seat's truncated string was
produced core-side (tool_search_catalog._short_desc 60-char manifest clip); the
plugin's registered WORKFLOW_PARAMS graph description must still carry the FULL
provider sentence verbatim. This pins it against future IN-PLUGIN truncation.
Row-1 root cause goes to cross_core upstream.

Stdlib-only, serial, prints PASS/FAIL lines, exit 0 = green (repo contract).
"""
import importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
sys.path.insert(0, str(BUILD))

import wfcommon  # noqa: E402

HOME = Path(tempfile.mkdtemp(prefix="wf-validator-caps-"))
os.environ["DUCKWORK_HOME"] = str(HOME)
spec = importlib.util.spec_from_file_location("door_caps", BUILD / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}" + (f"  << {detail}" if detail else "")
    ok += 1; print("PASS", msg)

def err_text(res):
    """All rejection strings of a _validation_error payload, joined."""
    if not res:
        return ""
    return res.get("error", "") + " || " + " || ".join(
        f"{e.get('field')}: {e.get('msg')}" for e in res.get("errors", []))

# --- (1) node max_turns=240: value AND cap, exact form ----------------------
g = {"name": "caps1", "nodes": [{"id": "a", "type": "agent", "goal": "g", "max_turns": 240}]}
res = door._validation_error(g)
check(res is not None, "max_turns=240 is rejected")
msgs = [e["msg"] for e in res["errors"] if e["field"] == "max_turns"]
check(len(msgs) == 1, "one max_turns error row", json.dumps(res))
m = msgs[0]
check("240" in m and "200" in m, "rejection names value 240 AND cap 200", m)
check(m == "max_turns 240 exceeds cap 200 (must be a number in (0, 200])",
      "exact exceeds-cap wording with parenthetical kept", m)

# --- (2) node timeout / run_budget: same shape ------------------------------
g2 = {"name": "caps2", "nodes": [{"id": "a", "type": "agent", "goal": "g",
                                  "timeout": 999999, "run_budget": 99999999}]}
res2 = door._validation_error(g2)
t = err_text(res2)
check("999999" in t and "86400" in t, "timeout/run_budget rows name value AND cap", t)
tm = [e["msg"] for e in res2["errors"] if e["field"] == "timeout"][0]
bm = [e["msg"] for e in res2["errors"] if e["field"] == "run_budget"][0]
check(tm == "timeout 999999 exceeds cap 86400 (must be a number in (0, 86400])",
      "node timeout exact exceeds-cap wording", tm)
check(bm == "run_budget 99999999 exceeds cap 86400 (must be a number in (0, 86400])",
      "node run_budget exact exceeds-cap wording", bm)

# --- (3) defaults.*: same shape ----------------------------------------------
g3 = {"name": "caps3", "defaults": {"max_turns": 240, "timeout": 999999},
      "nodes": [{"id": "a", "type": "agent", "goal": "g"}]}
res3 = door._validation_error(g3)
dm = {e["field"]: e["msg"] for e in res3["errors"]}
check("240" in dm.get("defaults.max_turns", "") and "200" in dm.get("defaults.max_turns", ""),
      "defaults.max_turns row names value 240 AND cap 200", json.dumps(res3))
check(dm.get("defaults.max_turns")
      == "max_turns 240 exceeds cap 200 (must be a number in (0, 200])",
      "defaults.max_turns exact exceeds-cap wording", dm.get("defaults.max_turns"))
check(dm.get("defaults.timeout")
      == "timeout 999999 exceeds cap 86400 (must be a number in (0, 86400])",
      "defaults.timeout exact exceeds-cap wording", dm.get("defaults.timeout"))

# --- (4) wfcommon._defaults_errors directly + untouched timeout_s path -------
de = [e["msg"] for e in wfcommon._defaults_errors({"max_turns": 240})]
check(de == ["max_turns 240 exceeds cap 200 (must be a number in (0, 200])"],
      "wfcommon._defaults_errors matches the door rows", json.dumps(de))
# test_waitgate_0923:61 matches the literal 'timeout_s must be a number' — that
# path (wfcommon wait-block validator) must be UNTOUCHED by this change.
wb = wfcommon.wait_spec_ok({"wait_s": 1, "timeout_s": 0})
check(any("timeout_s must be a number" in e["msg"] for e in wb),
      "wait-block timeout_s literal wording untouched", json.dumps(wb))

# --- (5) act_wait clamp kept + echo ------------------------------------------
# Hand-built committed run dir (no runner spawn needed; same trick as
# tests/test_sprint101_D-surface.py).
GRAPH = {"name": "caps-clamp", "nodes": [{"id": "one", "type": "agent", "goal": "offline"}]}
_orig_spawn = door._spawn_runner
door._spawn_runner = lambda r: None
try:
    r = HOME / "workflows" / "caps-clamp-1"
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(GRAPH))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": "/bin/false", "name": "caps-clamp"}))
    node = GRAPH["nodes"][0]
    (r / "nodes" / "one.json").write_text(json.dumps(
        {"status": "done", "output": {"ok": True}, "ms": 1,
         "efp": door._common.efp({node["id"]: node}, node)}))
    (r / "runner_exit.json").write_text(json.dumps({"reason": "done", "exit": 0}))

    w = door.act_wait({"run_id": r.name, "timeout": 7200})
    check("setup: clamped wait still lands on the committed status",
          w.get("status") == "done", json.dumps(w)[:200])
    check("clamped wait echoes the clamp",
          w.get("timeout_note") == "timeout clamped to 1800s (requested 7200)",
          json.dumps(w)[:200])
    w2 = door.act_wait({"run_id": r.name, "timeout": 600})
    check("no clamp under 1800: no timeout_note", "timeout_note" not in w2,
          json.dumps(w2)[:200])
    w3 = door.act_wait({"run_id": r.name, "timeout": 1800})
    check("boundary 1800 is not clamped", "timeout_note" not in w3,
          json.dumps(w3)[:200])
finally:
    door._spawn_runner = _orig_spawn
    shutil.rmtree(HOME, ignore_errors=True)

# --- (6) ROW 1 pin: registered graph description carries the FULL provider ---
# sentence verbatim (guards against future in-plugin truncation). The 60-char
# seat view and the ~500-char per-match grep view are core-side clips
# (_short_desc manifest clip + search_files' match clamp) — they never shorten
# what the model actually receives; the door registers the full string.
# digest 29d (0b680871): the description is built from adjacent short literals so a
# 500-char grep view shows meaningful windows — pin the SHAPE: no source line inside
# the graph-description block exceeds 520 chars (adjacent literals collapse in the
# AST, so this reads source). The runtime string itself is pinned verbatim below; a
# re-merge into one mega-line turns this red.
_desc_lines = (BUILD / "__init__.py").read_text().splitlines()
try:
    # F1 (deep review): anchor INSIDE the `"graph": {` block — a bare
    # `"description": (` search lands on WORKFLOW_SCHEMA's description (which is
    # legitimately three short lines) when the graph description is collapsed to
    # ONE plain literal without parens, making this pin vacuous in exactly the
    # mutation it advertises. Anchor: find `"graph": {`, then the first
    # `"description":` after it — and the shape MUST be the opening `(` form.
    _ig = next(i for i, l in enumerate(_desc_lines) if l.strip() == '"graph": {')
    _i0 = next(i for i in range(_ig, len(_desc_lines)) if '"description"' in _desc_lines[i])
    if not _desc_lines[_i0].strip().startswith('"description": ('):
        _wide = [f"{_i0+1}: graph description is a single literal, not adjacent literals"]
    else:
        _i1 = next(i for i in range(_i0, len(_desc_lines)) if _desc_lines[i].strip() == "),")
        _wide = [f"{i+1}:{len(_desc_lines[i])}" for i in range(_i0 + 1, _i1)
                 if len(_desc_lines[i]) > 520]
except StopIteration:
    _wide = ["description block not found (was it re-merged into one literal?)"]
check(not _wide, "graph description literals are grep-viewable (<520-char lines)", str(_wide))
PROVIDER_SENTENCE = ("provider (optional explicit Duckwork provider paired with model; "
                     "passed as --provider; when unset it is INHERITED from a "
                     "provider-qualified model alias/tier)")
desc = door.WORKFLOW_PARAMS["properties"]["graph"]["description"]
check(PROVIDER_SENTENCE in desc,
      "registered WORKFLOW_PARAMS graph description carries the full provider sentence verbatim",
      f"len(desc)={len(desc)}")
check(len(desc) > 1000, "description is not clip-sized (no 60-char collapse)",
      f"len(desc)={len(desc)}")

print(f"OK {ok} checks")
