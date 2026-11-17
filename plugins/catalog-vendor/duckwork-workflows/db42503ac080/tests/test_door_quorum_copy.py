#!/usr/bin/env python3
"""Door-copy pins for the fan-out quorum blurb (fb 2f9653b1cc98a4e0) and its
lane-mates (0b68087111f35d85 provider sentence, a045f659db56185d cap messaging).

The registered tool-schema description is what the seat reads at authoring time;
this test pins that door copy to the runner's real behavior:
  - quorum is OPTIONAL: stragglers are cancelled ONLY when it is set explicitly;
    with quorum unset the fan-out waits for every item (no default majority).
  - the provider sentence stays intact (no truncation regression).
  - numeric-bound rejections name both the value and the cap.
Stdlib-only; prints PASS/FAIL lines; exit 0 = green.
"""
import importlib.util, json, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

spec = importlib.util.spec_from_file_location("hw_door_quorum", root / "__init__.py")
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)

import wfcommon

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

# The REGISTERED description: the registry reads WORKFLOW_SCHEMA["parameters"],
# and that dict is the WORKFLOW_PARAMS constant itself.
desc = hw.WORKFLOW_SCHEMA["parameters"]["properties"]["graph"]["description"]
check("registered desc is the WORKFLOW_PARAMS constant",
      desc is hw.WORKFLOW_PARAMS["properties"]["graph"]["description"])

# est-2ek.1.80: the model sees this registered description before loading a skill.
class Ctx:
    def __init__(self): self.tools = {}
    def register_skill(self, *_, **__): pass
    def register_hook(self, *_, **__): pass
    def register_command(self, *_, **__): pass
    def register_tool(self, **kw): self.tools[kw["name"]] = kw
    def get_config(self, _key, default): return default
ctx = Ctx()
hw.register(ctx)
selection = ctx.tools["workflow"]["schema"]["description"]
check("registered selection names delegate_task", "delegate_task" in selection, selection)
check("registered selection names independent lanes / human gate / resumable graph",
      all(s in selection for s in ("independent lanes", "human gate", "resumable graph")), selection)
check("registered selection avoids one or two independent calls",
      "one or two independent calls" in selection, selection)

# (1) quorum copy follows the runner: optional, cancellation only when set,
#     no default majority anywhere.
check("quorum copy says OPTIONAL", "quorum (OPTIONAL" in desc,
      desc[desc.find("quorum ("):desc.find("quorum (") + 200] if "quorum (" in desc else "no 'quorum (' segment")
check("quorum copy: ONLY-when-set cancellation", "ONLY when set" in desc)
check("quorum copy: unset waits for every item", "waits for every item" in desc)
check("quorum copy keeps cancelled+failure-math semantics",
      "error_class 'cancelled'" in desc and "excluded from the failure math" in desc)
check("NO false default-majority claim", "default = majority" not in desc)
check("NO false floor(n/2) formula", "floor(n/2)" not in desc)

# (2) provider sentence intact (lane-mate 0b68087111f35d85: alleged truncation).
PROVIDER_SENT = ("provider (optional explicit Duckwork provider paired with model; "
                 "passed as --provider; when unset it is INHERITED from a "
                 "provider-qualified model alias/tier)")
check("provider sentence intact", PROVIDER_SENT in desc)

# (3) numeric-bound rejection names value AND cap (lane-mate a045f659db56185d).
errors = wfcommon.validate_graph_errors(
    [{"id": "n1", "type": "agent", "goal": "x", "max_turns": 240}])
msgs = [e["msg"] for e in errors]
check("max_turns=240 rejected", any("max_turns" in m for m in msgs), json.dumps(errors))
check("rejection names the value 240", any("240" in m for m in msgs), json.dumps(msgs))
check("rejection names the cap 200", any("cap 200" in m for m in msgs), json.dumps(msgs))

print("ALL-PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
