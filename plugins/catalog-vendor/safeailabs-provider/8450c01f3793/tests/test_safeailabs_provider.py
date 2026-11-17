from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DUCKWORK_ROOT = os.environ.get("DUCKWORK_AGENT_ROOT")

MODEL = "sail-frontier"


@pytest.fixture
def duckwork_providers(monkeypatch: pytest.MonkeyPatch):
    if not DUCKWORK_ROOT or not (Path(DUCKWORK_ROOT) / "providers" / "base.py").is_file():
        pytest.skip("set DUCKWORK_AGENT_ROOT to a Duckwork Agent checkout")

    monkeypatch.syspath_prepend(str(DUCKWORK_ROOT))
    # Duckwork imports a user plugin once per module name; drop it too so each test registers afresh.
    for module_name in list(sys.modules):
        if module_name == "providers" or module_name.startswith(("providers.", "_duckwork_user_provider_")):
            sys.modules.pop(module_name)
    return importlib.import_module("providers")


@pytest.fixture
def profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, duckwork_providers):
    plugin_dir = tmp_path / "plugins" / "safeailabs-provider"
    shutil.copytree(
        PLUGIN_ROOT,
        plugin_dir,
        ignore=shutil.ignore_patterns("tests", "__pycache__", ".git", ".pytest_cache", ".ruff_cache", ".env"),
    )
    layer = duckwork_providers._HomeLayer()
    monkeypatch.setattr(duckwork_providers, "_user_plugins_dir", lambda: None)
    monkeypatch.setattr(duckwork_providers, "_installed_plugins_dir", lambda: plugin_dir.parent)
    duckwork_providers._scan_home_layer(layer, "safeailabs-test-home")
    found = layer.registry.get("safeailabs")
    assert found is not None
    assert layer.aliases["safe-ai-labs"] == "safeailabs"
    return found


def test_registers_an_openai_compatible_api_key_provider(profile):
    assert profile.display_name == "Safe AI Labs"
    assert profile.api_mode == "chat_completions"
    assert profile.auth_type == "api_key"
    assert profile.base_url == "https://us.api.safeailabs.ai/v1"
    # The key, then the base URL a user sets to pick another region.
    assert profile.env_vars == ("SAFE_AI_KEY", "SAFE_AI_BASE_URL")


def test_lists_models_from_the_live_endpoint_with_a_fallback(profile):
    assert profile.supports_model_listing is True
    assert profile.fallback_models == (MODEL,)
    assert profile.default_aux_model == MODEL


def test_declares_the_models_context_window_and_leaves_output_to_the_server(profile):
    caps = profile.model_capabilities[MODEL]
    assert caps["context_window"] == 1_048_576
    assert caps["supports_tools"] is True
    assert caps["supports_reasoning"] is True
    assert caps["supports_vision"] is True
    # No max_tokens is sent unless the user sets one; the server's limit is 65,536.
    assert profile.get_max_tokens(MODEL) is None


def test_base_url_env_var_is_mirrored_into_the_auth_registry(profile, duckwork_providers):
    from duckwork_cli.auth_plugin_providers import _api_key_env_fields

    assert _api_key_env_fields(profile) == (("SAFE_AI_KEY",), "SAFE_AI_BASE_URL")


def test_a_timeout_only_providers_block_tunes_it_without_shadowing_it(duckwork_providers):
    # The README tells users to set providers.safeailabs.stale_timeout_seconds; that block carries
    # no endpoint, so it must not resolve as a custom provider of the same name.
    from duckwork_cli.providers import resolve_user_provider

    assert resolve_user_provider("safeailabs", {"safeailabs": {"stale_timeout_seconds": 3600}}) is None
