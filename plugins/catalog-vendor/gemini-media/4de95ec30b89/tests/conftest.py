# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
# Copyright 2026 bytecakelake
# SPDX-License-Identifier: Apache-2.0
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Provider tests subclass Duckwork's ABCs, so a Duckwork source tree must be importable.
_default_duckwork = Path(os.environ.get("LOCALAPPDATA", "")) / "duckwork" / "duckwork-agent"
DUCKWORK_DIR = Path(os.environ.get("DUCKWORK_AGENT_DIR", _default_duckwork))
if DUCKWORK_DIR.is_dir():
    sys.path.insert(0, str(DUCKWORK_DIR))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch, request):
    """Every test gets its own DUCKWORK_HOME and a clean in-memory model cache, and no real key."""
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "duckwork_home"))
    live = request.node.get_closest_marker("live") is not None
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_IMAGE_MODEL", "GEMINI_VIDEO_MODEL"):
        if live and name == "GEMINI_API_KEY":
            continue  # live tests need the real key
        monkeypatch.delenv(name, raising=False)
    from duckwork_gemini_media import models

    models.clear_cache()
    yield
    models.clear_cache()


class FakeAuth:
    """AuthStrategy stand-in that never reads the environment."""

    name = "fake"

    def __init__(self, configured=True, fingerprint="fp1"):
        self.configured = configured
        self._fp = fingerprint

    def is_configured(self):
        return self.configured

    def client_kwargs(self):
        return {"api_key": "unused"}

    def fingerprint(self):
        return self._fp

    def missing_message(self):
        return "missing"


@pytest.fixture
def fake_auth():
    return FakeAuth
