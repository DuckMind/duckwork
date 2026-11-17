"""Offline contract tests for the Chutes Duckwork provider."""

from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import re
import sys
import types
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPOSITORY_ROOT / "__init__.py"
README_PATH = REPOSITORY_ROOT / "README.md"
CI_WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
DEPENDABOT_WORKFLOW_PATH = (
    REPOSITORY_ROOT / ".github" / "workflows" / "dependabot-auto-merge.yml"
)
PACKAGE_PATH = REPOSITORY_ROOT / "duckwork_chutes_provider" / "__init__.py"
PYPROJECT_PATH = REPOSITORY_ROOT / "pyproject.toml"
MANIFEST_PATH = REPOSITORY_ROOT / "plugin.yaml"
CHANGELOG_PATH = REPOSITORY_ROOT / "CHANGELOG.md"
CITATION_PATH = REPOSITORY_ROOT / "CITATION.cff"
ISSUE_TEMPLATE_DIRECTORY = REPOSITORY_ROOT / ".github" / "ISSUE_TEMPLATE"
RELEASE_VERSION = "0.1.5"
RELEASE_DATE = "2026-08-09"


class ProviderProfile:
    """Minimal stand-in for Duckwork' ProviderProfile at the import boundary."""

    fallback_models = ()
    default_aux_model = ""
    models_url = ""
    default_headers: dict[str, str] = {}

    def __init__(self, **attributes: object) -> None:
        self.__dict__.update(attributes)


def load_directory_plugin(
    profile_type: type[ProviderProfile] = ProviderProfile,
) -> ProviderProfile:
    """Import the provider from its Duckwork user-plugin directory layout."""

    if not PLUGIN_PATH.is_file():
        raise AssertionError(f"missing directory plugin entry point: {PLUGIN_PATH}")

    registered: list[ProviderProfile] = []
    providers_module = types.ModuleType("providers")
    providers_module.register_provider = registered.append
    base_module = types.ModuleType("providers.base")
    base_module.ProviderProfile = profile_type

    module_name = "chutes_directory_plugin_under_test"
    module_names = ("providers", "providers.base", module_name)
    previous_modules = {name: sys.modules.get(name) for name in module_names}
    try:
        sys.modules["providers"] = providers_module
        sys.modules["providers.base"] = base_module
        spec = importlib.util.spec_from_file_location(
            module_name,
            PLUGIN_PATH,
            submodule_search_locations=[str(REPOSITORY_ROOT)],
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module
        for name in tuple(sys.modules):
            if name.startswith(f"{module_name}."):
                sys.modules.pop(name, None)

    if len(registered) != 1:
        raise AssertionError(f"expected one registered profile, got {len(registered)}")
    return registered[0]


@contextmanager
def stub_catalog_response(payload: bytes):
    """Stub Duckwork' credentialed opener with a bounded in-memory response."""

    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, size: int = -1) -> bytes:
            return payload if size < 0 else payload[:size]

    def open_credentialed_url(request, timeout):
        requests.append((request, timeout))
        return Response()

    duckwork_cli_module = types.ModuleType("duckwork_cli")
    duckwork_cli_module.__path__ = []
    security_module = types.ModuleType("duckwork_cli.urllib_security")
    security_module.open_credentialed_url = open_credentialed_url
    module_names = ("duckwork_cli", "duckwork_cli.urllib_security")
    previous_modules = {name: sys.modules.get(name) for name in module_names}
    try:
        sys.modules["duckwork_cli"] = duckwork_cli_module
        sys.modules["duckwork_cli.urllib_security"] = security_module
        yield requests
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module


class ChutesDirectoryPluginTests(unittest.TestCase):
    def test_release_metadata_is_consistent(self) -> None:
        changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
        citation = CITATION_PATH.read_text(encoding="utf-8")
        readme = README_PATH.read_text(encoding="utf-8")

        self.assertIn(
            f'__version__ = "{RELEASE_VERSION}"',
            PACKAGE_PATH.read_text(encoding="utf-8"),
        )
        self.assertIn(
            f'version = "{RELEASE_VERSION}"',
            PYPROJECT_PATH.read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"version: {RELEASE_VERSION}",
            MANIFEST_PATH.read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"## [{RELEASE_VERSION}] - {RELEASE_DATE}",
            changelog,
        )
        self.assertIn(
            f"version: {RELEASE_VERSION}",
            citation,
        )
        self.assertIn(
            f'date-released: "{RELEASE_DATE}"',
            citation,
        )
        self.assertIn(f"--branch v{RELEASE_VERSION}", readme)

    def test_registers_the_chutes_profile(self) -> None:
        profile = load_directory_plugin()

        self.assertEqual(profile.name, "chutes")
        self.assertEqual(profile.aliases, ("chutes-ai", "chutesai"))
        self.assertEqual(profile.api_mode, "chat_completions")
        self.assertEqual(profile.auth_type, "api_key")
        self.assertEqual(profile.base_url, "https://llm.chutes.ai/v1")
        self.assertEqual(
            profile.fallback_models,
            ("default:latency", "default:throughput"),
        )
        self.assertEqual(profile.default_aux_model, "")
        self.assertIs(profile.use_live_model_metadata, True)
        self.assertIs(profile.__dict__.get("use_live_model_metadata"), True)
        self.assertEqual(
            profile.env_vars, ("CHUTES_API_KEY", "CHUTES_BASE_URL")
        )

    def test_catalog_setup_failure_returns_none(self) -> None:
        profile = load_directory_plugin()

        self.assertIsNone(profile.fetch_models(base_url="://invalid"))

    def test_live_catalog_only_returns_tool_capable_models(self) -> None:
        profile = load_directory_plugin()
        payload = b'''{
            "data": [
                {"id": "tool-model", "supported_features": ["tools", "reasoning"]},
                {"id": "chat-only-model", "supported_features": ["reasoning"]},
                {"id": "unknown-model"},
                {"id": "null-features", "supported_features": null},
                {"id": 123, "supported_features": ["tools"]},
                {"supported_features": ["tools"]}
            ]
        }'''
        with stub_catalog_response(payload) as requests:
            metadata = profile.fetch_model_metadata(
                api_key="cpk_test-key",
                base_url="https://chutes.test/v1",
            )
            models = profile.fetch_models(
                api_key="cpk_test-key",
                base_url="https://chutes.test/v1",
            )

        self.assertEqual(
            metadata,
            [
                {
                    "id": "tool-model",
                    "supported_features": ["tools", "reasoning"],
                }
            ],
        )
        self.assertEqual(models, ["tool-model"])
        self.assertEqual(len(requests), 2)
        request, timeout = requests[0]
        self.assertEqual(request.full_url, "https://chutes.test/v1/models")
        self.assertEqual(request.get_header("Authorization"), "Bearer cpk_test-key")
        self.assertEqual(timeout, 8.0)

    def test_catalog_rejects_malformed_or_oversized_payloads(self) -> None:
        profile = load_directory_plugin()
        malformed_payloads = (
            b"null",
            b"{}",
            b'{"data": null}',
            b'{"data": "not-a-list"}',
        )

        for payload in malformed_payloads:
            with self.subTest(payload=payload):
                with stub_catalog_response(payload):
                    self.assertIsNone(profile.fetch_model_metadata())

        oversized_payload = b" " * (8 * 1024 * 1024 + 1)
        with stub_catalog_response(oversized_payload):
            self.assertIsNone(profile.fetch_model_metadata())

    def test_catalog_accepts_empty_list_payloads(self) -> None:
        profile = load_directory_plugin()

        for payload in (b"[]", b'{"data": []}'):
            with self.subTest(payload=payload):
                with stub_catalog_response(payload):
                    self.assertEqual(profile.fetch_model_metadata(), [])

    def test_catalog_supports_older_provider_profiles(self) -> None:
        class LegacyProviderProfile:
            fallback_models = ()
            default_aux_model = ""

            def __init__(self, **attributes: object) -> None:
                self.__dict__.update(attributes)

        profile = load_directory_plugin(LegacyProviderProfile)
        payload = b'{"data": [{"id": "tool-model", "supported_features": ["tools"]}]}'

        with stub_catalog_response(payload) as requests:
            self.assertEqual(
                profile.fetch_models(
                    api_key=None,
                    base_url="https://legacy-chutes.test/v1",
                ),
                ["tool-model"],
            )

        request, timeout = requests[0]
        self.assertEqual(request.full_url, "https://legacy-chutes.test/v1/models")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(timeout, 8.0)

    def test_catalog_honors_explicit_url_and_default_headers(self) -> None:
        profile = load_directory_plugin()
        profile.models_url = "https://catalog.chutes.test/models"
        profile.default_headers = {"X-Catalog-Test": "enabled"}
        payload = b'{"data": [{"id": "tool-model", "supported_features": ["TOOLS"]}]}'

        with stub_catalog_response(payload) as requests:
            self.assertEqual(
                profile.fetch_models(
                    api_key=None,
                    base_url="https://ignored.chutes.test/v1",
                ),
                ["tool-model"],
            )

        request, _timeout = requests[0]
        self.assertEqual(request.full_url, "https://catalog.chutes.test/models")
        self.assertEqual(request.get_header("X-catalog-test"), "enabled")
        self.assertIsNone(request.get_header("Authorization"))

    def test_readme_documents_current_and_future_install_paths(self) -> None:
        if not README_PATH.is_file():
            self.fail(f"missing README: {README_PATH}")

        readme = README_PATH.read_text(encoding="utf-8")
        self.assertIn("plugins/model-providers/chutes", readme)
        self.assertIn("Fordex/duckwork-agent#64277", readme)
        self.assertIn("duckwork plugins install", readme)
        self.assertIn("duckwork_agent.model_providers", readme)
        self.assertIn("default:latency", readme)
        self.assertIn("https://llm.chutes.ai/v1/models", readme)
        self.assertNotIn("deepseek-ai/DeepSeek-V3.2-TEE", readme)
        self.assertNotIn("??", readme)
        self.assertIn("Use the canonical `chutes` name", readme)
        self.assertIn("tool calling", readme)
        self.assertIn("model.context_length", readme)
        self.assertIn("https://github.com/Veightor/chutes-agent-toolkit", readme)
        self.assertNotIn("https://github.com/chutesai/chutes-agent-toolkit", readme)
        self.assertIn("Development checkout", readme)
        self.assertIn("## Project status", readme)
        self.assertIn("GitHub Releases only; not published to PyPI", readme)
        self.assertIn("Generic OpenAI-compatible transport", readme)

    def test_issue_forms_route_security_reports_and_guard_credentials(self) -> None:
        config = (ISSUE_TEMPLATE_DIRECTORY / "config.yml").read_text(
            encoding="utf-8"
        )
        bug_form = (ISSUE_TEMPLATE_DIRECTORY / "bug.yml").read_text(
            encoding="utf-8"
        )
        compatibility_form = (
            ISSUE_TEMPLATE_DIRECTORY / "compatibility.yml"
        ).read_text(encoding="utf-8")
        feature_form = (ISSUE_TEMPLATE_DIRECTORY / "feature_request.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("blank_issues_enabled: false", config)
        self.assertIn("security/advisories/new", config)
        self.assertIn('labels: ["bug"]', bug_form)
        self.assertIn('labels: ["compatibility"]', compatibility_form)
        self.assertIn('labels: ["enhancement"]', feature_form)
        for form in (bug_form, compatibility_form):
            with self.subTest(form=form[:40]):
                self.assertIn("Remove API keys", form)
                self.assertIn("required: true", form)

    def test_ci_runs_the_offline_contract_suite(self) -> None:
        if not CI_WORKFLOW_PATH.is_file():
            self.fail(f"missing CI workflow: {CI_WORKFLOW_PATH}")

        workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("Fordex/duckwork-agent", workflow)
        self.assertIn("3c27eb6234bf91b8ceee9e9071591b31e9b148cb", workflow)
        self.assertIn("3d3c42e5aac5ba805825da76410c181273ba90b1", workflow)
        self.assertIn("5fda3b95a4ea91299a34e894583c3862153e4b97", workflow)
        self.assertIn("DUCKWORK_SOURCE", workflow)
        self.assertIn("python -m pip wheel . --no-deps", workflow)
        self.assertIn('python-version: ["3.11", "3.12", "3.13", "3.14"]', workflow)
        self.assertEqual(workflow.count("persist-credentials: false"), 3)
        self.assertEqual(workflow.count("timeout-minutes:"), 2)
        self.assertNotIn("CHUTES_API_KEY", workflow)

    def test_github_actions_are_pinned_by_commit(self) -> None:
        for workflow_path in (CI_WORKFLOW_PATH, DEPENDABOT_WORKFLOW_PATH):
            workflow = workflow_path.read_text(encoding="utf-8")
            uses_lines = [
                line.strip()
                for line in workflow.splitlines()
                if re.match(r"^(?:-\s+)?uses:", line.strip())
            ]
            self.assertTrue(uses_lines, workflow_path)
            for uses_line in uses_lines:
                with self.subTest(workflow=workflow_path, uses=uses_line):
                    self.assertRegex(
                        uses_line,
                        re.compile(
                            r"^(?:-\s+)?uses: [^@\s]+@[0-9a-f]{40}(?:\s+#.*)?$"
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
