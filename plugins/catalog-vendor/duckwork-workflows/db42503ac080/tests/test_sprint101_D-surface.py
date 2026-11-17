#!/usr/bin/env python3
"""Sprint-101 lane D-surface, item #15 (O1-trimmed, 1.1): the inline card is
agent-authored — the auto-card hook machine is DELETED (wf-11 O1), so the
hook-registration, watching-session registration, interrupted-turn hold and
TTL-expiry assertions that referenced _LAUNCHED/_HELD/_auto_card are gone
with it. What remains:
 1. act_run's response carries no `card_rule` paste-prose anywhere (source + payload).
 2. act_run's payload carries the exact card, and the hint is the copy-exact
    paste line (papercut #70).
 3. status/wait payloads carry the same card for any reading session (the
    watching session gets the line in the payload; emitting it is the agent's
    job, not the backend's).
 4. The hook machine's symbols are gone from the shipped door module.

Run: /opt/duckwork/.venv/bin/python3 tests/test_sprint101_D-surface.py
"""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import importlib.util, json, os, shutil, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
HOME = ROOT / "home-s101d"
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/opt/duckwork")

spec = importlib.util.spec_from_file_location("wf_door_s101d", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

GRAPH = {"name": "s101d", "nodes": [{"id": "one", "type": "agent", "goal": "offline"}]}

def mk_run(rid, owner="other-session"):
    """Hand-built committed run dir so act_wait/act_status need NO runner spawn."""
    r = HOME / "workflows" / rid
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(GRAPH))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": "/bin/false", "name": "s101d",
                                            "owner": {"session_id": owner}}))
    node = GRAPH["nodes"][0]
    (r / "nodes" / "one.json").write_text(json.dumps(
        {"status": "done", "output": {"ok": True}, "ms": 1,
         "efp": door._common.efp({node["id"]: node}, node), "fp_rule_version": door._common.FP_RULE_VERSION}))
    (r / "runner_exit.json").write_text(json.dumps({"reason": "done", "exit": 0}))
    return r

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)
_orig_spawn = door._spawn_runner
door._spawn_runner = lambda r: None

CARD = lambda rid: f'::workflow{{id="{rid}"}}'

try:
    # ---- 1: no card_rule anywhere (payload + source of truth) ----------------
    os.environ["DUCKWORK_SESSION_ID"] = "session-a"
    out = door.act_run({"graph": dict(GRAPH)})
    rid = out.get("run_id", "")
    check("act_run returns a run_id + card", bool(rid) and out.get("card") == CARD(rid), json.dumps(out)[:200])
    check("act_run response carries NO card_rule", "card_rule" not in out, json.dumps(out)[:200])
    src = (ROOT / "__init__.py").read_text(encoding="utf-8")
    check("no card_rule key remains in __init__.py", '"card_rule"' not in src)
    # O1 copy-exact hint (papercut #70): the hint names the paste line verbatim.
    check("hint is the copy-exact paste line",
          out.get("hint", "").startswith("PASTE this line alone in your reply")
          and CARD(rid) in out.get("hint", ""), repr(out.get("hint"))[:200])

    # ---- 2: any reading session gets the card in the payload -----------------
    os.environ["DUCKWORK_SESSION_ID"] = "watcher"
    rid2 = "s101d-watch-1"
    mk_run(rid2, owner="launcher-elsewhere")
    w = door.act_wait({"run_id": rid2, "timeout": 0})
    check("setup: act_wait on a committed run returns status", w.get("status") == "done", json.dumps(w)[:160])
    check("act_wait payload carries the card for the watching session",
          w.get("card") == CARD(rid2), json.dumps(w)[:200])
    s = door.act_status({"run_id": rid2})
    check("act_status payload carries the card", s.get("card") == CARD(rid2), json.dumps(s)[:200])

    # ---- 4: the hook machine is gone from the shipped module -----------------
    for sym in ("_auto_card", "_note_launch", "_clear_launch", "_take_held",
                "_visible_cards", "_LAUNCHED", "_HELD", "_HELD_TTL_SECONDS",
                "_LAUNCH_LOCK", "_VISIBLE_CARD_RE", "_CARD_ATTR_RE"):
        check(f"symbol {sym} no longer exists on the door", not hasattr(door, sym))
    # #157 re-armed exactly ONE hook (the card-enforcement last-resort shipper);
    # the O1 law still holds for the deleted auto-card machine: no other hook.
    check("exactly one register_hook call remains, the #157 card-enforcement hook",
          src.count("register_hook") == 1
          and 'register_hook("transform_llm_output"' in src)
finally:
    door._spawn_runner = _orig_spawn
    shutil.rmtree(HOME, ignore_errors=True)

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
