"""Command Code credential fallback and badge regression tests."""

import json
import pathlib
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_providers import commandcode


class CommandCodeCredentialsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.auth_path = pathlib.Path(self.temp.name) / "auth.json"
        patcher = mock.patch.object(commandcode, "_AUTH_PATH", str(self.auth_path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _duckwork_resolver(self, value=None, *, error=None):
        resolver = mock.Mock(side_effect=error) if error else mock.Mock(return_value=(value, "pool"))
        config = types.SimpleNamespace(auth_type="api_key")
        auth = types.ModuleType("duckwork_cli.auth")
        auth.__dict__["PROVIDER_REGISTRY"] = {"commandcode": config}
        auth.__dict__["_resolve_api_key_provider_secret"] = resolver
        package = types.ModuleType("duckwork_cli")
        package.__path__ = []
        return resolver, mock.patch.dict(sys.modules, {"duckwork_cli": package, "duckwork_cli.auth": auth})

    def test_cli_key_takes_precedence_over_duckwork(self):
        self.auth_path.write_text(json.dumps({"apiKey": "cli-key"}), encoding="utf-8")
        resolver, modules = self._duckwork_resolver("duckwork-key")
        with modules:
            self.assertEqual("cli-key", commandcode._load_api_key())
        resolver.assert_not_called()

    def test_missing_cli_file_uses_duckwork_key(self):
        resolver, modules = self._duckwork_resolver("duckwork-key")
        with modules:
            self.assertEqual("duckwork-key", commandcode._load_api_key())
        resolver.assert_called_once_with("commandcode", mock.ANY)

    def test_invalid_cli_key_uses_duckwork_key(self):
        self.auth_path.write_text(json.dumps({"apiKey": "   "}), encoding="utf-8")
        _, modules = self._duckwork_resolver("duckwork-key")
        with modules:
            self.assertEqual("duckwork-key", commandcode._load_api_key())

    def test_unavailable_duckwork_resolver_returns_no_key(self):
        _, modules = self._duckwork_resolver(error=RuntimeError("locked store"))
        with modules:
            self.assertIsNone(commandcode._load_api_key())

    def test_official_command_code_badge_is_inlined(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "desktop" / "plugin.js").read_text(encoding="utf-8")
        self.assertTrue(re.search(r"commandcode:\s*\{\s*viewBox:\s*\"0 0 137 137\"", source))
        self.assertIn("m93.6604 26.1784", source)


if __name__ == "__main__":
    unittest.main()
