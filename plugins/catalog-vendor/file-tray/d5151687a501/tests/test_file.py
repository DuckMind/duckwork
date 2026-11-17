"""Local checks that do not require Duckwork."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DUCKWORK_HOME"] = tempfile.mkdtemp(prefix="file-tray-test-")

import file_hooks
import file_store
import file_tools


def test_normalize() -> None:
    assert file_store.normalize_path(r"C:\Users\aydin\a.py") == "C:/Users/aydin/a.py"
    assert file_store.normalize_path("  ./src/main.ts  ") == "./src/main.ts"
    assert file_store.normalize_path("https://example.com/x") is None
    assert file_store.normalize_path("a\nb") is None


def test_read_write() -> None:
    file_store.clear_files()
    file_hooks.on_post_tool_call(
        "read_file",
        {"path": "plugins/file-tray/file_store.py"},
        json.dumps({"ok": True}),
    )
    file_hooks.on_post_tool_call(
        "write_file",
        {"path": "plugins/file-tray/README.md", "content": "x"},
        json.dumps({"ok": True}),
    )
    items = file_store.list_files()
    assert len(items) == 2
    paths = {it["path"] for it in items}
    assert "plugins/file-tray/file_store.py" in paths
    assert "plugins/file-tray/README.md" in paths
    actions = {it["path"]: it["action"] for it in items}
    assert actions["plugins/file-tray/file_store.py"] == "read"
    assert actions["plugins/file-tray/README.md"] == "write"


def test_patch_and_dedupe() -> None:
    file_store.clear_files()
    file_hooks.on_post_tool_call(
        "patch",
        {"path": "app.py", "old_string": "a", "new_string": "b"},
        json.dumps({"ok": True}),
    )
    file_hooks.on_post_tool_call(
        "patch",
        {"path": "app.py", "old_string": "b", "new_string": "c"},
        json.dumps({"ok": True}),
    )
    items = file_store.list_files()
    assert len(items) == 1
    assert items[0]["action"] == "patch"


def test_v4a_paths() -> None:
    file_store.clear_files()
    body = (
        "*** Begin Patch\n"
        "*** Update File: src/a.ts\n"
        "@@\n-old\n+new\n"
        "*** Add File: src/b.ts\n"
        "+hello\n"
        "*** End Patch"
    )
    file_hooks.on_post_tool_call(
        "patch",
        {"mode": "patch", "patch": body},
        json.dumps({"ok": True}),
    )
    paths = {it["path"] for it in file_store.list_files()}
    assert "src/a.ts" in paths
    assert "src/b.ts" in paths


def test_ignore_terminal() -> None:
    file_store.clear_files()
    file_hooks.on_post_tool_call(
        "terminal",
        {"command": "cat README.md"},
        json.dumps({"exit_code": 0, "output": "ok"}),
    )
    assert file_store.list_files() == []


def test_tools_json() -> None:
    file_store.clear_files()
    data = json.loads(file_tools.file_tray_list({}, extra="x"))
    assert data["ok"] is True
    assert data["count"] == 0
    assert "(file-tray is empty)" in data["markdown"]
    cleared = json.loads(file_tools.file_tray_clear({}))
    assert cleared["ok"] is True


if __name__ == "__main__":
    test_normalize()
    test_read_write()
    test_patch_and_dedupe()
    test_v4a_paths()
    test_ignore_terminal()
    test_tools_json()
    print("ok")
