#!/usr/bin/env python3
"""#172: bind a real review target; keep the README invocation and link honest."""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon

spec = importlib.util.spec_from_file_location("door172", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)

graph = json.loads((ROOT / "examples/review/portable-review.workflow.json").read_text())
assert wfcommon.validate_graph_errors(graph) == []
nodes = {node["id"]: node for node in graph["nodes"]}
assert set(nodes) == {"recon", "review", "summary"}
assert "{run.target_dir}" in nodes["recon"]["goal"], "recon needs an explicit target"
assert "current directory" not in nodes["recon"]["goal"].lower()
assert "target_dir" in graph["description"] and "run_context" in graph["description"]

readme = (ROOT / "examples/README.md").read_text()
# Exercise the complete JSON invocation actually printed in the map README.
examples = re.findall(r"```jsonc\s*workflow\s*(.*?)\s*```", readme, re.S)
invocation = next(json.loads(text) for text in examples if "portable-review.workflow.json" in text)
assert invocation["action"] == "run"
assert invocation["graph_path"].endswith("/examples/review/portable-review.workflow.json")
bound = door._bind_run_context(wfcommon.apply_graph_defaults(graph), invocation["run_context"])
bound_nodes = {node["id"]: node for node in bound["nodes"]}
assert invocation["run_context"]["target_dir"] in bound_nodes["recon"]["goal"]
assert "{run." not in bound_nodes["recon"]["goal"]
assert "{item}" in bound_nodes["review"]["fanout"]["goal"]
for binding in ({}, {"other": "value"}):
    try:
        door._bind_run_context(graph, binding)
    except ValueError:
        pass
    else:
        raise AssertionError("missing target seed must reject")

row = next(line for line in readme.splitlines() if "portable-review" in line)
assert "target_dir" in row
link = re.search(r"\[`wf/1`\]\(([^)]+)\)", readme).group(1)
assert (ROOT / "examples" / link).is_file(), "README grammar link must resolve"
print("PASS portable-review seed binding, README invocation, missing-seed rejection, grammar link")
