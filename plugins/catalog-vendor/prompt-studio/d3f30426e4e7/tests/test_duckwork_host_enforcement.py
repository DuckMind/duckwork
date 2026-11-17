"""Enforcement (#31): only dashboard/duckwork_host.py imports Duckwork; routes and engines go through it."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"

SIBLINGS = {"duckwork_host", "llm_adapter", "suggest_engine", "session_context", "plugin_api"}
THIRD_PARTY_OK = {"fastapi", "pydantic"}


def _top_level_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", getattr(func, "id", ""))
            if name in ("import_module", "__import__") and node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str) and not node.args[0].value.startswith("."):
                yield node.lineno, node.args[0].value


def test_only_the_host_module_imports_duckwork():
    allowed = set(sys.stdlib_module_names) | THIRD_PARTY_OK | SIBLINGS
    offenders = []
    for path in sorted(DASHBOARD.glob("*.py")):
        if path.name == "duckwork_host.py":
            continue
        for line, module in _top_level_imports(path):
            if module.split(".")[0] not in allowed:
                offenders.append(f"{path.name}:{line} imports {module}")
    assert not offenders, "Duckwork symbols must come through duckwork_host: " + "; ".join(offenders)


def test_the_scan_catches_a_duckwork_import_and_a_dynamic_one(tmp_path):
    sample = tmp_path / "engine.py"
    sample.write_text("import json\nfrom agent.redact import x\nimport importlib\nimportlib.import_module('duckwork_cli.config')\n"
                      "importlib.import_module(f'.{1}', __package__)\nfrom . import llm_adapter\n")
    assert sorted(module for _, module in _top_level_imports(sample)) == ["agent.redact", "duckwork_cli.config", "importlib", "json"]


def test_the_contract_lists_the_code_and_every_keyword_the_adapter_sends():
    contract = (ROOT / "docs" / "CONTRACT.md").read_text(encoding="utf-8")
    sys.path.insert(0, str(DASHBOARD))
    import duckwork_host

    assert "`host_incompatible`" in contract and duckwork_host.CODE == "host_incompatible"
    assert "## Duckwork host" in contract
    for keyword in duckwork_host.CALL_LLM_KWARGS:
        assert f"`{keyword}`" in contract, keyword


def test_the_host_files_carry_no_machine_paths_or_install_ids():
    """The host module and its tests name no maintainer machine: placeholders only (Codex round 1)."""
    import re
    personal = re.compile(r"/root/|/home/[a-z]|/Users/|/usr/local/lib/duckwork|\b[0-9a-f]{32}\b|\b[0-9a-f]{16}\b")
    files = [DASHBOARD / "duckwork_host.py", *sorted((ROOT / "tests").glob("test_duckwork_host*.py"))]
    hits = [f"{f.name}:{n}: {line.strip()[:80]}" for f in files
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
            if personal.search(line) and "personal = re.compile" not in line]
    assert hits == []
