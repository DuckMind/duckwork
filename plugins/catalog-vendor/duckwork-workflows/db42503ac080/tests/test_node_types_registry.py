"""jam-h24 node-types registry: NODE_TYPES is the ONE table.
Pins the contract every converted site leans on:
  (1) NODE_TYPES has exactly agent|gate|echo with the closed key-sets;
  (2) the schedule hook: agent spawns, gate holds, echo commits verbatim;
  (3) kind() gives the implicit-agent default, and an unknown type can never
      match any scheduling branch (fallback spawns matches no True/False/None);
  (4) validation behavior unchanged through the table: unknown type keeps the
      byte-identical error, unknown keys still name the type's allowed set.
"""
import importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
_spec = importlib.util.spec_from_file_location("_wfcommon_under_test", HERE.parent / "wfcommon.py")
wfcommon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wfcommon)

failures = []
def check(cond, label):
    print(("PASS" if cond else "FAIL") + " " + label)
    if not cond:
        failures.append(label)

NT = wfcommon.NODE_TYPES
check(set(NT) == {"agent", "gate", "echo"}, "NODE_TYPES is exactly agent|gate|echo")
check(NT["agent"].keys is wfcommon.AGENT_KEYS
      and NT["gate"].keys is wfcommon.GATE_KEYS
      and NT["echo"].keys is wfcommon.ECHO_KEYS,
      "closed key-sets come from the registry (same objects as AGENT/GATE/ECHO_KEYS)")
check(NT["agent"].spawns is True and NT["gate"].spawns is False and NT["echo"].spawns is None,
      "schedule hook: agent spawns / gate holds / echo commits verbatim")

check(wfcommon.kind({"id": "a"}).spawns is True, "kind() defaults an untyped node to the agent kind")
for bad in ("weird", "AGENT", ""):
    fb = wfcommon.kind({"id": "x", "type": bad})
    check(fb.spawns not in (True, False, None),
          f"kind() fallback for unknown type {bad!r} matches no scheduling branch")

errs = wfcommon.validate_graph_errors([{"id": "a", "type": "robot", "goal": "g"}])
check(any(e["field"] == "type" and e["msg"] == "type must be agent|gate|echo" for e in errs),
      "unknown type error text is byte-identical through the table")
errs = wfcommon.validate_graph_errors([{"id": "e", "type": "echo", "after": [], "output": "x", "goal": "nope"}])
check(any(e["field"] == "goal" and "unknown key" in e["msg"]
          and '"output"' in e["msg"] and '"goal"' not in e["msg"] for e in errs),
      "echo closed-key rejection names ECHO_KEYS from the registry")
check(wfcommon.validate_graph_errors(
        [{"id": "e", "type": "echo", "after": [], "output": "x"}]) == [],
      "a valid echo graph still validates clean")

print("ALL PASS" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
