"""Backlink providers consume only explicitly injected child environment keys."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("requests")
import backlinks_auth  # noqa: E402


def test_static_provider_keys_come_from_env(monkeypatch):
    monkeypatch.setenv("MOZ_API_KEY", "moz-key")
    monkeypatch.setenv("BING_WEBMASTER_API_KEY", "bing-key")
    monkeypatch.setenv("KEYWORDSEVERYWHERE_API_KEY", "keywords-key")

    assert backlinks_auth.get_moz_api_key() == "moz-key"
    assert backlinks_auth.get_bing_api_key() == "bing-key"
    assert backlinks_auth.get_keywordseverywhere_api_key() == "keywords-key"


def test_legacy_credential_store_is_never_opened(monkeypatch, tmp_path):
    legacy = tmp_path / "backlinks-api.json"
    legacy.write_text('{"moz_api_key":"legacy"}')

    def deny_file_access(*_args, **_kwargs):
        raise AssertionError("credential store must not be opened")

    monkeypatch.delenv("MOZ_API_KEY", raising=False)
    monkeypatch.setattr(builtins, "open", deny_file_access)

    assert backlinks_auth.get_moz_api_key() is None
    assert legacy.exists()


def test_commoncrawl_cache_remains_nonsecret_runtime_state(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(backlinks_auth, "CACHE_DIR", str(cache_dir / "commoncrawl"))

    assert backlinks_auth.get_cache_dir() == str(cache_dir / "commoncrawl")
    assert (cache_dir / "commoncrawl").is_dir()
