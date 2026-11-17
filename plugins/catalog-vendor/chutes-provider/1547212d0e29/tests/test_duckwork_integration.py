"""Integration contract against a local Duckwork Agent checkout."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DUCKWORK_SOURCE = os.environ.get("DUCKWORK_SOURCE", "")
DUCKWORK_PYTHON = os.environ.get("DUCKWORK_PYTHON", sys.executable)


@unittest.skipUnless(DUCKWORK_SOURCE, "set DUCKWORK_SOURCE to run Duckwork integration tests")
class DuckworkIntegrationTests(unittest.TestCase):
    def test_user_directory_plugin_registers_profile_and_aliases(self) -> None:
        duckwork_source = Path(DUCKWORK_SOURCE).resolve()
        self.assertTrue((duckwork_source / "providers" / "__init__.py").is_file())

        with tempfile.TemporaryDirectory() as temporary_directory:
            duckwork_home = Path(temporary_directory) / "duckwork-home"
            target = duckwork_home / "plugins" / "model-providers" / "chutes"
            target.parent.mkdir(parents=True)
            shutil.copytree(
                REPOSITORY_ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"),
            )

            environment = os.environ.copy()
            environment["DUCKWORK_HOME"] = str(duckwork_home)
            environment["PYTHONPATH"] = str(duckwork_source)
            environment["CHUTES_API_KEY"] = "cpk_test-key"
            environment["CHUTES_BASE_URL"] = "https://chutes.test/v1"

            program = """
from providers import get_provider_profile

profile = get_provider_profile("chutes")
assert profile is not None
assert profile.name == "chutes"
assert get_provider_profile("chutes-ai") is profile
assert get_provider_profile("chutesai") is profile
assert profile.base_url == "https://llm.chutes.ai/v1"
assert profile.env_vars == ("CHUTES_API_KEY", "CHUTES_BASE_URL")
assert profile.fallback_models == ("default:latency", "default:throughput")
assert profile.default_aux_model == ""
assert profile.use_live_model_metadata is True

from duckwork_cli.auth import PROVIDER_REGISTRY, resolve_provider
assert "chutes" in PROVIDER_REGISTRY
assert resolve_provider("chutes-ai") == "chutes"
assert resolve_provider("chutesai") == "chutes"

from duckwork_cli.models import CANONICAL_PROVIDERS
assert any(entry.slug == "chutes" for entry in CANONICAL_PROVIDERS)

from duckwork_cli.runtime_provider import resolve_runtime_provider
runtime = resolve_runtime_provider(requested="chutes")
assert runtime["provider"] == "chutes"
assert runtime["api_key"] == "cpk_test-key"
assert runtime["base_url"] == "https://chutes.test/v1"

from duckwork_cli.doctor import _build_apikey_providers_list
rows = [row for row in _build_apikey_providers_list() if row[0] == "Chutes"]
assert len(rows) == 1
assert rows[0][1] == ("CHUTES_API_KEY",)
assert rows[0][2] == "https://llm.chutes.ai/v1/models"
assert rows[0][3] == "CHUTES_BASE_URL"
"""
            result = subprocess.run(
                [DUCKWORK_PYTHON, "-c", program],
                cwd=duckwork_source,
                env=environment,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
