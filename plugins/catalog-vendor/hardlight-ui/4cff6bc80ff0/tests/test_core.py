"""Deterministic core contracts; no project code is executed."""
import importlib.util
import os
from pathlib import Path
import shutil

import pytest


def test_contrast_known_values_and_explicit_roles():
    from hardlight.contrast import check_contrast
    result = check_contrast([
        {"foreground": "#000", "background": "#FFF", "role": "text"},
        {"foreground": "#777777", "background": "#ffffff", "role": "large_text", "label": "Heading"},
        {"foreground": "#777777", "background": "#ffffff", "role": "text"},
        {"foreground": "#070707", "background": "#777777", "role": "text"},
    ])
    assert result["ok"] is True
    assert result["pairs"][0]["ratio"] == 21.0
    assert result["pairs"][1]["status"] == "pass"
    assert result["pairs"][2]["status"] == "fail"
    assert result["pairs"][2]["ratio"] < 4.5
    assert result["pairs"][1]["label"] == "Heading"
    assert round(result["pairs"][3]["ratio"], 2) == 4.5
    assert result["pairs"][3]["status"] == "fail"  # Never compare the rounded display value.


@pytest.mark.parametrize("pairs", [[], [{}], [True], [{"foreground": "red", "background": "#fff", "role": "text"}], [{"foreground": "#0008", "background": "#fff", "role": "ui"}], [{"foreground": "#000", "background": "#fff"}], [{"foreground": "#000", "background": "#fff", "role": True}], [{"foreground": "#000", "background": "#fff", "role": "text"}] * 101])
def test_contrast_invalid_inputs_fail(pairs):
    from hardlight.contrast import check_contrast
    result = check_contrast(pairs)
    assert result["ok"] is False
    assert result["error"]
    assert "pairs" not in result


def test_shipped_library_is_allowlisted_and_style_exact():
    from hardlight.library import get_reference
    index = get_reference()
    assert index["ok"] is True
    assert "navigation" in index["topics"]
    atlas = get_reference("atlas")
    assert atlas["ok"] is True
    assert len(atlas["styles"]) >= 16
    packet = get_reference("style", "swiss-editorial")
    assert packet["style"]["id"] == "swiss-editorial"
    assert packet["sources"]
    assert get_reference("style", "Swiss-editorial")["ok"] is False
    assert get_reference("../../.env")["ok"] is False
    assert get_reference("style")["ok"] is False
    for topic in index["topics"]:
        if topic not in {"index", "atlas", "style"}:
            ref = get_reference(topic)
            assert ref["ok"] is True, ref
            assert len(ref["content"]) > 100


def test_wheel_layout_reference_resources_are_inside_package(tmp_path):
    root = Path(__file__).resolve().parents[1]
    package = tmp_path / "site-packages" / "hardlight"
    package.mkdir(parents=True)
    shutil.copyfile(root / "hardlight" / "library.py", package / "library.py")
    shutil.copytree(root / "data", package / "data")
    spec = importlib.util.spec_from_file_location("hardlight_wheel_library", package / "library.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.get_reference("style", "quiet-craft")["ok"] is True


def test_direction_preserves_brief_offers_structural_options_and_authority():
    from hardlight.direction import make_direction
    brief = "  Research workspace for field botanists.\nOffline collections matter.  "
    plan = make_direction(brief)
    assert plan["ok"] is True
    assert plan["brief"] == brief
    assert len(plan["candidates"]) == 3
    assert len({tuple(p["composition"]) for p in plan["candidates"]}) == 3
    assert plan["ia_questions"] and plan["state_matrix"] and plan["verification_plan"]
    explicit = make_direction(brief, styles=["kinetic-poster", "quiet-craft"])
    assert [p["id"] for p in explicit["candidates"]] == ["kinetic-poster", "quiet-craft"]
    for authority in ("refinement", "extension"):
        result = make_direction(brief, authority=authority)
        assert result["preserve_incumbent"] is True
        assert result["missing_context"]
    assert make_direction("x", surface="bogus")["ok"] is False
    assert make_direction("x", authority="bogus")["ok"] is False
    assert make_direction(" ")["ok"] is False
    assert make_direction("x", styles=["unknown"])["ok"] is False
    assert make_direction("x", styles="quiet-craft")["ok"] is False
    assert make_direction("x", styles=[])["ok"] is False


def test_inspection_reports_provenance_and_never_reads_excluded_files(tmp_path):
    tmp_path = tmp_path.resolve()  # macOS temporary roots can contain /var -> /private/var.
    from hardlight.inspection import inspect_project
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        result = inspect_project(str(tmp_path))
        assert result["ok"] is False and "no-follow" in result["error"]
        return  # This platform explicitly fails closed rather than weakening traversal safety.
    (tmp_path / "index.html").write_text('<main><img src="x.png"><a href="#">Go</a></main>')
    (tmp_path / "theme.css").write_text(':root {\n --canvas: #fff;\n --space: 1rem;\n}\nbutton:focus { outline: none; }')
    for folder in ("node_modules", ".private", "dist", "vendor"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "hidden.css").write_text('--secret: yes;')
    (tmp_path / "credentials.ts").write_text('const secret = "never read";')
    (tmp_path / "data.json").write_text('{"secret":"never read"}')
    (tmp_path / "linked.css").symlink_to(tmp_path / "theme.css")
    (tmp_path / "big.css").write_bytes(b"x" * (512 * 1024 + 1))
    result = inspect_project(str(tmp_path))
    assert result["ok"] is True
    assert {f["path"] for f in result["inventory"]} == {"index.html", "theme.css"}
    canvas = next(t for t in result["tokens"] if t["name"] == "--canvas")
    assert canvas["value"] == "#fff"
    assert canvas["path"] == "theme.css" and canvas["line"] == 2
    assert {f["rule"] for f in result["findings"]} >= {"image-alt", "placeholder-link", "focus-outline"}
    for finding in result["findings"]:
        assert set(("path", "line", "rule", "severity", "evidence", "recovery", "method")) <= finding.keys()
    assert result["coverage"]["partial"] is True
    assert result["coverage"]["limitations"]
    assert len(result["skipped"]) >= 8
    assert inspect_project(str(tmp_path), max_files=1)["coverage"]["partial"] is True
    assert inspect_project(str(tmp_path), max_files=True)["ok"] is False
    assert inspect_project(str(tmp_path), max_files=501)["ok"] is False
    assert inspect_project(str(tmp_path / "missing"))["ok"] is False
    linked = tmp_path / "linked-root"
    linked.symlink_to(tmp_path, target_is_directory=True)
    assert inspect_project(str(linked))["ok"] is False


def test_inspection_bounds_traversal_and_labels_jsx_heuristics(tmp_path):
    tmp_path = tmp_path.resolve()
    from hardlight.inspection import inspect_project
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        result = inspect_project(str(tmp_path))
        assert result["ok"] is False and "no-follow" in result["error"]
        return  # This platform explicitly fails closed rather than weakening traversal safety.
    (tmp_path / "view.tsx").write_text('export const X = () => <img src="art.svg" />;')
    for i in range(160):
        (tmp_path / f"dir-{i:03}").mkdir()
    result = inspect_project(str(tmp_path))
    assert result["coverage"]["directories_seen"] <= 128
    assert result["coverage"]["partial"] is True
    # The bounded scan may stop before the root file, but it must explain that.
    if result["findings"]:
        assert all(f["method"] == "heuristic" for f in result["findings"])


def test_inspection_total_entry_budgets_and_special_files(tmp_path):
    tmp_path = tmp_path.resolve()
    from hardlight.inspection import inspect_project
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        assert inspect_project(str(tmp_path))["ok"] is False
        return
    for index in range(18):
        (tmp_path / f"large-{index:02}.css").write_bytes(b" " * (512 * 1024))
    result = inspect_project(str(tmp_path), max_files=500)
    assert result["coverage"]["bytes_read"] <= 8 * 1024 * 1024
    assert result["coverage"]["budget_hit"] is True
    assert result["coverage"]["files_read"] == 16
    root = tmp_path / "entries"
    root.mkdir()
    for index in range(5020):
        (root / f"unsupported-{index}.txt").touch()
    result = inspect_project(str(root))
    assert result["coverage"]["entries_seen"] <= 5000
    assert result["coverage"]["budget_hit"] is True
    special = tmp_path / "special"
    special.mkdir()
    os.mkfifo(special / "pipe.css")
    (special / "binary.ts").write_bytes(b"\0\0")
    (special / "latin.css").write_bytes(b"\xff")
    (special / "safe.css").write_text("button {color: black;}")
    (special / "symlink-dir").symlink_to(root, target_is_directory=True)
    result = inspect_project(str(special))
    assert [item["path"] for item in result["inventory"]] == ["safe.css"]
    assert {item["reason"] for item in result["skipped"]} >= {"symlink", "not a regular file", "binary content", "unsupported encoding; requires UTF-8"}


@pytest.mark.parametrize("surface", ["marketing", "product", "reading", "commerce", "portfolio"])
def test_every_surface_has_three_distinct_reference_based_defaults(surface):
    from hardlight.direction import make_direction
    result = make_direction("Distinct product-specific brief", surface=surface)
    assert result["ok"] is True
    assert len(result["candidates"]) == 3
    assert len({item["id"] for item in result["candidates"]}) == 3
    for item in result["candidates"]:
        assert item["sources"] and item["signature"] and item["mobile"]


@pytest.mark.parametrize("pairs", [None, {}, True, [False], [{"foreground": "#000", "background": "#fff", "role": "text", "label": False}], [{"foreground": "#000\n", "background": "#fff", "role": "text"}]])
def test_contrast_rejects_nonopaque_and_malformed_shapes(pairs):
    from hardlight.contrast import check_contrast
    assert check_contrast(pairs)["ok"] is False
