"""Portable authoring skill contract; no provider or live-home dependencies."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
skill = (root / "SKILL.md").read_text(encoding="utf-8")
assert skill.startswith("---\n")
front, body = skill.split("---\n", 2)[1:]
match = re.search(r'^description:\s*["\']?([^\n"\']+)', front, re.M)
assert match is not None
desc = match.group(1)
assert all(word in desc[:57].lower() for word in ("workflow", "fan-out", "audit", "census")), desc
assert len(desc) <= 60, desc
assert len(skill.splitlines()) < 110, len(skill.splitlines())
assert "cheapest tier" not in skill.lower()
assert "haus " not in skill.lower()
assert "/opt/duckwork" not in skill
assert "```json" not in skill  # main guide should not duplicate reference grammar
assert "card" in skill and "alone" in skill, "SKILL.md must tell the agent to paste the card line alone"
assert "composer" in skill, "SKILL.md must say the strip shows this chat's runs regardless"
assert "graph_path" in skill and "proposed" not in skill.lower()
assert "interrupted" in skill
assert "seat default" in skill.lower() and "not" in skill.lower()
assert all((root / "references" / f).is_file() for f in ("grammar.md", "operations.md", "development.md"))
assert "agent.when" in (root / "references/grammar.md").read_text()
_ver = re.search(r"^version:\s*([\d.]+)", (root / "plugin.yaml").read_text(), re.M).group(1)
assert f"workflow {_ver}" in (root / "references/grammar.md").read_text().lower(), f"grammar.md must name {_ver}"
assert f"version: {_ver}" in skill, f"SKILL.md front-matter must name {_ver}"
# A6 drift guard: every shape row in budgets.md must equal SHAPE_PRESETS exactly.
import sys as _sys
_sys.path.insert(0, str(root))
import wfcommon as _wfc
_budgets = (root / "references/budgets.md").read_text(encoding="utf-8")
_rows = dict((m[0], (int(m[1]), int(m[2]))) for m in
             re.findall(r"^\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", _budgets, re.M))
assert set(_rows) == set(_wfc.SHAPE_PRESETS), f"budgets.md shapes {_rows} != SHAPE_PRESETS"
for _shape, _preset in _wfc.SHAPE_PRESETS.items():
    assert _rows[_shape] == (_preset["max_turns"], _preset["timeout"]), \
        f"budgets.md row {_shape}={_rows[_shape]} drifts from SHAPE_PRESETS {_preset}"
print("ALL PASS: portable workflow skill")
