"""Contract tests for the Opper provider profile.

Runs against a Duckwork Agent checkout on ``PYTHONPATH`` (see the workflow) and
exercises the *real* discovery path: the plugin is copied into a temporary
``$DUCKWORK_HOME/plugins/duckwork-opper/`` exactly as ``duckwork plugins install``
lays it out, then resolved through ``providers.get_provider_profile``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

providers = pytest.importorskip("providers", reason="needs a duckwork-agent checkout on PYTHONPATH")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _reset_discovery() -> None:
    """Forget every registered profile and the imported user-plugin module so
    the next ``get_provider_profile`` call re-runs discovery from scratch."""
    providers._REGISTRY.clear()
    providers._ALIASES.clear()
    providers._PROVIDER_LIST_CACHE = None
    providers._discovered = False
    for name in [m for m in sys.modules if m.startswith("_duckwork_user_provider_")]:
        sys.modules.pop(name, None)


@pytest.fixture
def opper_profile(tmp_path, monkeypatch):
    dest = tmp_path / "plugins" / "duckwork-opper"
    dest.mkdir(parents=True)
    for name in ("__init__.py", "plugin.yaml"):
        shutil.copy(PLUGIN_ROOT / name, dest / name)
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path))
    monkeypatch.delenv("OPPER_BASE_URL", raising=False)
    _reset_discovery()
    profile = providers.get_provider_profile("opper")
    assert profile is not None, "opper profile must be discovered from $DUCKWORK_HOME/plugins/duckwork-opper"
    yield profile
    _reset_discovery()


class TestIdentity:
    def test_core_fields(self, opper_profile):
        p = opper_profile
        assert p.name == "opper"
        assert p.api_mode == "chat_completions"
        assert p.auth_type == "api_key"
        assert p.base_url == "https://api.opper.ai/v3/compat"
        assert p.env_vars == ("OPPER_API_KEY", "OPPER_BASE_URL")
        assert p.hostname in ("", "api.opper.ai")

    def test_aliases_resolve(self, opper_profile):
        for alias in ("opper-ai", "opperai", "opper.ai"):
            assert providers.get_provider_profile(alias) is opper_profile

    def test_display_metadata(self, opper_profile):
        assert opper_profile.display_name == "Opper"
        assert opper_profile.description
        assert opper_profile.signup_url.startswith("https://")


class TestCatalog:
    def test_fallback_models_are_pool_names(self, opper_profile):
        # Bare pool names, never vendor-pinned routes: Opper picks the provider.
        assert opper_profile.fallback_models
        for model in opper_profile.fallback_models:
            assert "/" not in model, f"{model!r} must be a bare Opper pool name"

    def test_aux_model_is_in_fallbacks(self, opper_profile):
        assert opper_profile.default_aux_model in opper_profile.fallback_models

    def test_models_url_defaults_to_base(self, opper_profile):
        assert opper_profile.models_url in ("", "https://api.opper.ai/v3/compat/models")


class TestListing:
    def test_listed_once(self, opper_profile):
        names = [p.name for p in providers.list_providers()]
        assert names.count("opper") == 1
