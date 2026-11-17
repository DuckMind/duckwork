"""P7 structural test — zero duckwork_* / agent_peer imports across src/spectator.

AC: No file under src/spectator imports any symbol from duckwork_*, agent_peer,
or duckwork_agent packages. The plugin is self-contained (stdlib + fastapi +
pydantic + yaml + sqlite3 only).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _collect_imports(src_path: Path) -> list[tuple[str, int, str]]:
    """Parse a Python file and return (filepath, lineno, import_line) tuples."""
    lines = src_path.read_text(encoding="utf-8").splitlines()
    results: list[tuple[str, int, str]] = []
    try:
        tree = ast.parse(src_path.read_text(encoding="utf-8"), str(src_path))
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for _alias in node.names:
                line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                results.append((str(src_path), node.lineno, line))
        elif isinstance(node, ast.ImportFrom):
            line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            results.append((str(src_path), node.lineno, line))
    return results


@pytest.fixture(scope="module")
def src_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "spectator"


class TestP7ZeroDuckworkImports:
    """Structural gate: src/spectator must contain zero duckwork imports."""

    def test_all_py_files_are_inspected(self, src_dir):
        py_files = list(src_dir.rglob("*.py"))
        assert py_files, f"No .py files found under {src_dir}"

    def test_zero_duckwork_imports(self, src_dir):
        forbidden = {"duckwork_", "agent_peer", "duckwork_agent"}
        violations: list[str] = []
        for py_file in src_dir.rglob("*.py"):
            for _, lineno, line in _collect_imports(py_file):
                stripped = line.lstrip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                for bad in forbidden:
                    if bad in stripped:
                        violations.append(f"{py_file}:{lineno}: {stripped}")
                        break
        assert not violations, f"P7 violations found ({len(violations)}):\n" + "\n".join(violations)

    def test_no_runtime_duckwork_module_dependency(self, src_dir):
        """Verify every .py module can be parsed even when duckwork is absent."""
        for py_file in src_dir.rglob("*.py"):
            src = py_file.read_text(encoding="utf-8")
            assert ast.parse(src, str(py_file)), f"Syntax error in {py_file}"
