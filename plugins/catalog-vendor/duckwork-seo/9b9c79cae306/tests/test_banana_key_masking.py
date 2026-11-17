"""The Banana setup check reports key presence without printing key material."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKEwxyz"


def _load(monkeypatch, home: Path, name: str):
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("GOOGLE_AI_API_KEY", FAKE_KEY)
    spec = importlib.util.spec_from_file_location(
        f"banana_{name}", REPO_ROOT / f"extensions/banana/scripts/{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name,call", [
    ("validate_setup", lambda m: m.main()),
])
def test_key_characters_are_not_shown(monkeypatch, tmp_path, capsys, name, call):
    module = _load(monkeypatch, tmp_path, name)
    monkeypatch.setattr(sys, "argv", [name, "--model", "gemini-test-image"])
    call(module)
    out = capsys.readouterr().out
    assert FAKE_KEY not in out
    assert "wxyz" not in out
