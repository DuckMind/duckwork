"""Opt-in normal catalog installation on an unmodified Duckwork release.

Installs the published media and model pins in disposable profiles, then runs
the media pin's own real-host checks. No inference or generation is submitted.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request


def main():
    source = Path(os.environ['DUCKWORK_SOURCE']).resolve()
    duckwork_sha = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    assert duckwork_sha == os.environ['DUCKWORK_EXPECTED_SHA'], duckwork_sha
    url = 'https://duckwork-agent.fordex.com/docs/api/plugin-catalog.json'
    with urllib.request.urlopen(url, timeout=30) as response:
        catalog = json.load(response)
    entries = {row['name']: row for row in catalog['entries']
               if row['name'] in {'acedatacloud', 'acedatacloud-media'}}
    assert len(entries) == 2, entries
    assert len(entries['acedatacloud-media']['capabilities']['provides_tools']) == 32

    for mode in ['in_process', 'host']:
        with tempfile.TemporaryDirectory(prefix='duckwork-ace-published-') as directory:
            profile = Path(directory)
            env = {key: value for key, value in os.environ.items() if key in {
                'PATH', 'HOME', 'LANG', 'TMPDIR', 'DUCKWORK_RUNTIME_DIR',
                'SSL_CERT_FILE', 'SSL_CERT_DIR', 'HTTP_PROXY', 'HTTPS_PROXY',
                'ALL_PROXY', 'NO_PROXY',
            }}
            env.update(DUCKWORK_HOME=str(profile), PYTHONPATH=str(source),
                       DUCKWORK_PYTHON=sys.executable, COLUMNS='180')

            def run(*args, extra_env=None):
                result = subprocess.run(
                    [sys.executable, *args], cwd=profile,
                    env={**env, **(extra_env or {})}, text=True,
                    capture_output=True, timeout=300,
                )
                print(result.stdout, end='', flush=True)
                if result.stderr:
                    print(result.stderr, file=sys.stderr, end='', flush=True)
                result.check_returncode()
                return result.stdout

            version = run('-m', 'duckwork_cli.main', '--version')
            search = run('-m', 'duckwork_cli.main', 'plugins', 'search', 'acedatacloud')
            brand_search = {}
            for term in ['Suno', 'Seedance', 'Happy Horse', 'GPT Image', 'Nano Banana']:
                result = run('-m', 'duckwork_cli.main', 'plugins', 'search', term)
                assert 'acedatacloud-media' in result, (term, result)
                brand_search[term] = 'acedatacloud-media'
            installed = {}
            for name, entry in entries.items():
                assert name in search, search
                info = run('-m', 'duckwork_cli.main', 'plugins', 'info', name)
                assert entry['sha'][:8] in info, info
                run('-m', 'duckwork_cli.main', 'plugins', 'install', name, '--enable')
                root = profile / 'plugins' / name
                sha = subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
                assert sha == entry['sha'], (name, sha, entry['sha'])
                installed[name] = {'sha': sha, 'tier': entry['tier'],
                                   'version': entry['version'], 'repo': entry['repo']}

            from ruamel.yaml import YAML
            yaml = YAML()
            config_file = profile / 'config.yaml'
            config = yaml.load(config_file.read_text()) or {}
            assert set(entries) <= set(config['plugins']['enabled']), config
            config['plugins']['isolation'] = mode
            with config_file.open('w') as stream:
                yaml.dump(config, stream)
            media = profile / 'plugins' / 'acedatacloud-media'
            specs = [json.loads(p.read_text()) for p in (media / 'services').glob('*.json')]
            assert len(specs) == 17
            assert {t for s in specs for t in s['tools']} == set(
                entries['acedatacloud-media']['capabilities']['provides_tools'])
            # This runs the installed, reviewed pin's existing checks, not a
            # locally copied candidate package or an injected catalog.
            run(str(media / 'scripts' / 'check_runtime.py'), '--child', mode)
            run('-c', """
from providers import get_provider_profile
from duckwork_cli.models import list_available_providers
from duckwork_cli.runtime_provider import resolve_runtime_provider
p = get_provider_profile('acedatacloud')
assert p is not None
row = next(r for r in list_available_providers() if r['id'] == 'acedatacloud')
assert row['label'] == 'Ace Data Cloud' and row['authenticated']
r = resolve_runtime_provider(requested='acedatacloud', target_model='gpt-4.1-mini')
assert r['provider'] == 'acedatacloud'
assert r['api_mode'] == 'chat_completions'
assert r['base_url'] == 'https://api.acedata.cloud/openai'
assert set(p.fallback_models) == {'gpt-4.1-mini', 'gpt-4.1'}
""", extra_env={'ACEDATACLOUD_API_KEY': 'synthetic-discovery-only'})
            print(json.dumps({
                'published_catalog_install': 'passed', 'mode': mode,
                'host_sha': duckwork_sha, 'host_version_display': version.strip(),
                'installed': installed, 'services': 17, 'tools': 32,
                'brand_search': brand_search,
                'paid_calls': 0,
            }), flush=True)


if __name__ == '__main__':
    main()
