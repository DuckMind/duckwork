"""Explicit context improves the worksheet, not deterministic artistic judgment."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hardlight.direction import make_direction

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {
    "audience": "  Print-room operators\nOn shared tablets.  ",
    "tasks": ["Find a job", "Leave a useful handoff note"],
    "content": ["Four fictional job jackets"],
    "assets": ["Original local cover SVG"],
    "identity": "Preserve blue stock and the job-jacket structure",
    "browsers": "Current Chrome, Firefox and Safari; useful fallback required",
    "constraints": ["Offline", "Session-only changes"],
}


def test_context_is_preserved_and_gaps_are_specific():
    result = make_direction("A print room", authority="extension", context=CONTEXT)
    assert result["ok"], result
    assert result["context"] == CONTEXT
    assert result["missing_context"] == []
    assert result["preserve_incumbent"] is True
    assert result["design_contract"]["status"] == "awaiting_host_authorship"
    fields = result["design_contract"]["decisions"]
    assert {x["id"] for x in fields} == {"thesis", "structure", "invariants", "signature", "mobile", "budget", "critique"}
    assert all(x["status"] == "not_authored" and x["prompt"] for x in fields)
    assert "preserve" in next(x["prompt"] for x in fields if x["id"] == "structure").lower()
    assert {"layout", "platform", "performance"} <= set(result["craft_references"])
    assert all(x["status"] == "not_run" for x in result["verification_matrix"])
    partial = make_direction("x", context={"audience": "Readers"})
    assert not any(x.startswith("audience:") for x in partial["missing_context"])
    assert any(x.startswith("tasks:") for x in partial["missing_context"])


def test_context_copies_caller_lists_and_does_not_change_default_selection():
    context = copy.deepcopy(CONTEXT)
    old = make_direction("Original brief", surface="reading")
    result = make_direction("Original brief", surface="reading", context=context)
    assert result["candidates"] == old["candidates"]
    result["context"]["tasks"].append("caller must not see this")
    assert context == CONTEXT
    explicit = make_direction("x", context={}, styles=["quiet-craft"])
    assert [s["id"] for s in explicit["candidates"]] == ["quiet-craft"]
    assert old["brief"] == "Original brief"


@pytest.mark.parametrize("context", [
    [], True, "audience", {"unknown": "x"}, {"audience": False}, {"audience": " "},
    {"identity": "x" * 2001}, {"tasks": "x"}, {"tasks": []}, {"tasks": [1]},
    {"tasks": [" "]}, {"tasks": ["x"] * 13}, {"tasks": ["x" * 1001]},
    {"tasks": ["x" * 1000] * 12, "content": ["x" * 1000] * 5},
])
def test_invalid_context_returns_json_error(context):
    result = make_direction("x", context=context)
    assert result["ok"] is False
    assert "context" in result["error"]
    json.dumps(result, allow_nan=False)


def test_context_exact_limits_and_none_are_supported():
    assert make_direction("x", context=None)["ok"]
    assert make_direction("x", context={})["ok"]
    assert make_direction("x", context={"audience": "x" * 2000, "tasks": ["x" * 1000] * 12, "identity": "x" * 2000})["ok"]


def test_cli_context_round_trip(tmp_path):
    payload = tmp_path / "direction.json"
    payload.write_text(json.dumps({"brief": "Print room", "context": CONTEXT}), encoding="utf-8")
    run = subprocess.run([sys.executable, "-m", "hardlight", "direction", "--input", str(payload)], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["context"] == CONTEXT


@pytest.mark.parametrize("name", ["print-room", "incident-desk", "field-journal"])
def test_fixed_briefs_preserve_facts_without_claiming_completed_design(name):
    payload = json.loads((ROOT / "examples/briefs" / f"{name}.json").read_text(encoding="utf-8"))
    result = make_direction(**payload)
    assert result["ok"], result
    assert result["brief"] == payload["brief"]
    assert result["context"] == payload["context"]
    assert result["missing_context"] == []
    assert result["design_contract"]["status"] == "awaiting_host_authorship"
    assert all(check["status"] == "not_run" for check in result["verification_matrix"])
