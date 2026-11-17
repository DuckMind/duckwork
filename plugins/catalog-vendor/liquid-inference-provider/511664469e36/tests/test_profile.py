import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).parent.parent


@dataclass
class ProviderProfile:
    name: str
    aliases: tuple[str, ...] = ()
    display_name: str = ""
    description: str = ""
    signup_url: str = ""
    env_vars: tuple[str, ...] = ()
    base_url: str = ""
    auth_type: str = "api_key"
    default_headers: dict[str, str] = field(default_factory=dict)
    default_aux_model: str = ""
    fallback_models: tuple[str, ...] = ()

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return {}, {}


# Duckwork Agent is not installable from PyPI, so stand-ins supply its two names.
def load_profile() -> Any:
    registered: list[Any] = []
    providers = types.ModuleType("providers")
    providers.register_provider = registered.append
    base = types.ModuleType("providers.base")
    base.ProviderProfile = ProviderProfile
    with mock.patch.dict(sys.modules, {"providers": providers, "providers.base": base}):
        spec = importlib.util.spec_from_file_location("liquid_plugin", ROOT / "__init__.py")
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    (profile,) = registered
    return profile


class ProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_profile()

    def test_registers_one_api_key_provider(self) -> None:
        self.assertEqual(self.profile.name, "liquid")
        self.assertEqual(self.profile.aliases, ("liquid-inference",))
        self.assertEqual(self.profile.auth_type, "api_key")
        self.assertEqual(self.profile.base_url, "https://router.inference.ai.exchange/v1")
        self.assertEqual(self.profile.env_vars, ("LIQUID_API_KEY", "LIQUID_BASE_URL"))

    def test_each_request_has_the_client_label_and_a_cap(self) -> None:
        self.assertEqual(self.profile.default_headers["X-Title"], "Duckwork Agent")
        self.assertGreater(float(self.profile.default_headers["x-liquid-cap-usd"]), 0)

    def test_sends_only_a_selected_reasoning_effort(self) -> None:
        extras = self.profile.build_api_kwargs_extras
        self.assertEqual(
            extras(reasoning_config={"enabled": True, "effort": "high"}),
            ({}, {"reasoning_effort": "high"}),
        )
        for config in (None, {}, {"enabled": False}, {"enabled": False, "effort": "none"}):
            self.assertEqual(extras(reasoning_config=config), ({}, {}))
        self.assertEqual(extras(reasoning_config={"effort": "none"}), ({}, {}))
        self.assertIsNot(
            type(self.profile).build_api_kwargs_extras, ProviderProfile.build_api_kwargs_extras
        )

    def test_the_manifest_declares_a_model_provider(self) -> None:
        manifest = (ROOT / "plugin.yaml").read_text()
        self.assertIn("\nkind: model-provider\n", manifest)
        self.assertIn("- name: LIQUID_API_KEY", manifest)


if __name__ == "__main__":
    unittest.main()
