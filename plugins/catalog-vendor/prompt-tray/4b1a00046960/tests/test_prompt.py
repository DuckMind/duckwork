"""Local checks that do not require Duckwork."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DUCKWORK_HOME"] = tempfile.mkdtemp(prefix="prompt-tray-test-")

import prompt_store
import prompt_tools


def test_seed() -> None:
    items = prompt_store.list_prompts()
    titles = {it["title"] for it in items}
    assert titles == {"Review", "Plan", "Explain"}


def test_add_and_list_tool() -> None:
    added = prompt_store.add_prompt("Fix", "Fix the bug. Do not expand scope.")
    assert added["ok"] is True
    assert added["item"]["title"] == "Fix"
    data = json.loads(prompt_tools.prompt_tray_list({}))
    assert data["ok"] is True
    assert data["count"] >= 4
    assert "Fix" in data["markdown"]


def test_reject_empty() -> None:
    bad = prompt_store.add_prompt("  ", "")
    assert bad["ok"] is False


def test_delete() -> None:
    added = prompt_store.add_prompt("Temp", "temporary body")
    item_id = added["item"]["id"]
    gone = prompt_store.delete_prompt(item_id)
    assert gone["ok"] is True
    ids = {it["id"] for it in prompt_store.list_prompts()}
    assert item_id not in ids


def test_tool_kwargs() -> None:
    data = json.loads(prompt_tools.prompt_tray_list({}, extra="x"))
    assert data["ok"] is True


if __name__ == "__main__":
    test_seed()
    test_add_and_list_tool()
    test_reject_empty()
    test_delete()
    test_tool_kwargs()
    print("ok")
