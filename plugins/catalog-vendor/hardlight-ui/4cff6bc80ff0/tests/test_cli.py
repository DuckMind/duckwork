"""CLI exercises exactly the same dictionary-producing core functions."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    result = subprocess.run([sys.executable, "-m", "hardlight", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
    return result, json.loads(result.stdout)


def test_cli_contrast_and_json_errors(tmp_path):
    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps([{"foreground": "#000", "background": "#fff", "role": "text"}]))
    process, result = run_cli("contrast", "--pairs", str(pairs))
    assert process.returncode == 0 and result["pairs"][0]["ratio"] == 21
    process, result = run_cli("contrast", "--pairs", str(tmp_path / "missing.json"))
    assert process.returncode != 0 and result["ok"] is False
    pairs.write_text("not JSON")
    process, result = run_cli("contrast", "--pairs", str(pairs))
    assert process.returncode != 0 and result["ok"] is False
    for args in [(), ("bogus",), ("contrast",), ("inspect", ".", "--max-files", "true")]:
        process, result = run_cli(*args)
        assert process.returncode != 0 and result["ok"] is False


def test_cli_reference_direction_navigation_and_lazy_browser(tmp_path):
    process, styles = run_cli("styles")
    assert process.returncode == 0 and len(styles["styles"]) >= 16
    process, ref = run_cli("reference", "style", "--style", "quiet-craft")
    assert process.returncode == 0 and ref["style"]["id"] == "quiet-craft"
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"brief": "A collection tool", "surface": "product", "styles": ["wayfinding"]}))
    process, direction = run_cli("direction", "--input", str(brief))
    assert process.returncode == 0 and direction["candidates"][0]["id"] == "wayfinding"
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"pages": [{"id": "home", "label": "Home", "links": []}], "tasks": []}))
    process, navigation = run_cli("navigation", "--input", str(graph))
    assert process.returncode == 0 and navigation["ok"] is True
    process, error = run_cli("browser", "https://example.com", "--output-dir", str(tmp_path / "browser"))
    assert process.returncode != 0 and error["ok"] is False
    # Core use must never import Playwright or the optional browser runner.
    probe = subprocess.run([sys.executable, "-c", "import sys; from hardlight.cli import main; main(['contrast','--pairs',sys.argv[1]]); assert 'playwright' not in sys.modules; assert 'hardlight.browser' not in sys.modules", str(tmp_path / "nonexistent")], cwd=ROOT, capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr


def test_cli_inspect_uses_shared_result(tmp_path):
    from hardlight.inspection import inspect_project
    (tmp_path / "index.html").write_text('<img src="a">')
    process, result = run_cli("inspect", str(tmp_path))
    expected = inspect_project(str(tmp_path))
    assert result == expected
    assert process.returncode == (0 if expected["ok"] else 1)
