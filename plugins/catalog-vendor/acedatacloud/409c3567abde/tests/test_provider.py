"""Behavior contracts against a real Duckwork checkout, without account credentials.

DUCKWORK_SOURCE=/path/to/duckwork-agent python -m unittest discover -s tests -v
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
DUCKWORK = Path(os.environ["DUCKWORK_SOURCE"]).resolve()


class ProviderIntegrationTests(unittest.TestCase):
    def run_duckwork(self, source, *, install=True):
        with tempfile.TemporaryDirectory(prefix="duckwork-acedatacloud-test-") as temp:
            home = Path(temp)
            if install:
                destination = home / "plugins" / "acedatacloud"
                destination.mkdir(parents=True)
                for name in ("__init__.py", "plugin.yaml", "README.md"):
                    shutil.copy2(PLUGIN / name, destination / name)
                (home / "config.yaml").write_text(
                    "plugins:\n  enabled: [acedatacloud]\n", encoding="utf-8"
                )
            env = {
                key: value
                for key, value in os.environ.items()
                if key in {"PATH", "SYSTEMROOT", "LANG", "TMP", "TEMP"}
            }
            env.update(
                DUCKWORK_HOME=str(home),
                DUCKWORK_RUNTIME_DIR=str(home / "runtime"),
                PYTHONPATH=str(DUCKWORK),
                ACEDATACLOUD_API_KEY="test-key-not-a-credential",
            )
            result = subprocess.run(
                [sys.executable, "-c", source],
                cwd=home,
                env=env,
                text=True,
                capture_output=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

    def test_install_registers_named_provider_and_runtime_credentials(self):
        self.run_duckwork(
            """
from providers import get_provider_profile
from duckwork_cli.providers import resolve_provider_full, determine_api_mode
from duckwork_cli.auth import resolve_api_key_provider_credentials
from duckwork_cli.models import list_available_providers

p = get_provider_profile('acedatacloud')
assert p is not None
assert p.display_name == 'Ace Data Cloud'
from urllib.parse import parse_qs, urlsplit
signup = urlsplit(p.signup_url)
assert signup.netloc == 'platform.acedata.cloud' and signup.path == '/console/applications'
assert parse_qs(signup.query) == {
    'utm_source': ['opensource'], 'utm_medium': ['referral'],
    'utm_campaign': ['evergreen'], 'utm_content': ['duckwork_model_picker_api_key'],
}
resolved = resolve_provider_full('acedatacloud')
assert resolved.id == 'acedatacloud'
assert resolved.base_url == 'https://api.acedata.cloud/openai'
assert determine_api_mode('acedatacloud') == 'chat_completions'
credentials = resolve_api_key_provider_credentials('acedatacloud')
assert credentials['api_key'] == 'test-key-not-a-credential'
assert credentials['base_url'] == 'https://api.acedata.cloud/openai'
row = next(p for p in list_available_providers() if p['id'] == 'acedatacloud')
assert row['authenticated']
assert row['label'] == 'Ace Data Cloud'
print('Named provider, protocol and profile-scoped credentials resolved')
"""
        )
        self.run_duckwork(
            """
from providers import get_provider_profile
assert get_provider_profile('acedatacloud') is None
print('A separate uninstalled profile has no Ace Data Cloud provider')
""",
            install=False,
        )

    def test_live_catalog_filter_and_unavailable_catalog(self):
        self.run_duckwork(
            """
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from providers import get_provider_profile

requests = []
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append((self.path, self.headers.get('Authorization')))
        if self.path == '/unavailable/models':
            self.send_response(503)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'data': [{'id': name} for name in [
            'gpt-image-2', 'gpt-4.1', 'claude-sonnet-5-5', 'gpt-4.1-mini',
            'unknown-new-model'
        ]]}).encode())
    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    profile = get_provider_profile('acedatacloud')
    base = f'http://127.0.0.1:{server.server_port}'
    assert profile.fetch_models(api_key='catalog-test', base_url=base) == [
        'gpt-4.1', 'gpt-4.1-mini'
    ]
    assert requests[0] == ('/models', 'Bearer catalog-test')
    assert profile.fetch_models(base_url=base + '/unavailable') is None
    assert set(profile.fallback_models) == {'gpt-4.1', 'gpt-4.1-mini'}
    print('Live catalog excludes unsupported IDs, honors base URL, handles 503')
finally:
    server.shutdown()
    server.server_close()
    thread.join()
"""
        )


if __name__ == "__main__":
    unittest.main()
