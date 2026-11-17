"""Exercise a single consolidated plugin through real Duckwork discovery; no API calls.

Run with the Duckwork interpreter and DUCKWORK_SOURCE set. Each run creates a fresh
home containing only this plugin. It never uses the user's normal profile.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def child(mode):
    from agent.secret_scope import reset_secret_scope, set_secret_scope
    from duckwork_cli.plugins import discover_plugins, get_plugin_manager, get_plugin_toolsets
    from tools.registry import registry
    from toolsets import resolve_toolset
    from model_tools import get_tool_definitions
    from agent.image_gen_registry import get_provider

    discover_plugins()
    manager = get_plugin_manager()
    specs = [json.loads(p.read_text()) for p in sorted((ROOT / 'services').glob('*.json'))]
    expected_sets = {s['toolset'] for s in specs}
    expected_tools = {t for s in specs for t in s['tools']}
    rows = {r[0] for r in get_plugin_toolsets()}
    assert expected_sets <= rows, (expected_sets - rows, mode)
    assert len(expected_tools) == 32 and len(expected_sets) == 17
    assert all(name.startswith('acedatacloud_') for name in expected_tools)
    assert all(name.startswith('acedatacloud-') for name in expected_sets)
    for name in expected_tools:
        assert registry.get_entry(name.replace('acedatacloud_', 'acedata_', 1), scope=manager.scope_key) is None
    for spec in specs:
        assert set(resolve_toolset(spec['toolset'])) == set(spec['tools'])
        for name in spec['tools']:
            entry = registry.get_entry(name, scope=manager.scope_key)
            assert entry and entry.toolset == spec['toolset']
        result = registry.dispatch(spec['generate_name'], {'unknown': True}, scope=manager.scope_key)
        result = json.loads(result) if isinstance(result, str) else result
        assert result['error']['code'] == 'invalid_parameters', (spec['service'], result)

    provider = get_provider('acedatacloud-nano-banana')
    assert provider and provider.list_models()[0]['id'] == 'nano-banana-2-lite'
    assert provider.get_setup_schema()['env_vars'][0]['key'] == 'ACEDATACLOUD_API_KEY'
    assert provider.capabilities()['max_reference_images'] == 4
    assert not provider.is_available()
    # No dispatch uses valid parameters, so the synthetic key cannot make a request.
    token = set_secret_scope({'ACEDATACLOUD_API_KEY': 'synthetic-not-a-real-key'})
    try:
        if mode == 'in_process':
            assert provider.is_available()
            for spec in specs:
                defs = get_tool_definitions(enabled_toolsets=[spec['toolset']], quiet_mode=True,
                                            skip_tool_search_assembly=True)
                names = {x['function']['name'] for x in defs}
                assert names & expected_tools == set(spec['tools']), (spec['toolset'], names)
                disabled = get_tool_definitions(enabled_toolsets=list(expected_sets),
                                               disabled_toolsets=[spec['toolset']], quiet_mode=True,
                                               skip_tool_search_assembly=True)
                names = {x['function']['name'] for x in disabled}
                assert not names.intersection(spec['tools'])
                assert (expected_tools - set(spec['tools'])) <= names
    finally:
        reset_secret_scope(token)
    assert not provider.is_available()
    # The normal tools CLI offers/persists each independent service toggle.
    commands = [
        ['tools', 'disable', 'acedatacloud-veo'],
        ['tools', 'enable', 'acedatacloud-suno'],
        ['tools', 'list'],
    ]
    for command in commands:
        run = subprocess.run([sys.executable, '-m', 'duckwork_cli.main', *command],
                             capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, (command, run.stdout, run.stderr)
        if command == ['tools', 'list']:
            for key in expected_sets:
                assert key in run.stdout, (mode, key)
    from duckwork_cli.config import load_config
    from duckwork_cli.tools_config import _get_platform_tools
    enabled = _get_platform_tools(load_config(), 'cli', include_default_mcp_servers=False)
    assert 'acedatacloud-suno' in enabled and 'acedatacloud-veo' not in enabled, enabled
    manager.unload()
    print(json.dumps({'mode': mode, 'services': 17, 'registered_tools': 32,
                      'native_image_provider': True, 'independent_cli_selection': True,
                      'paid_calls': 0, 'passed': True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', choices=['in_process', 'host'])
    args = parser.parse_args()
    if args.child:
        child(args.child)
        return
    source = Path(os.environ['DUCKWORK_SOURCE']).resolve()
    for mode in ['in_process', 'host']:
        with tempfile.TemporaryDirectory(prefix='duckwork-acedatacloud-media-') as tmp:
            home = Path(tmp)
            destination = home / 'plugins/acedatacloud-media'
            shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns(
                '.git', 'artifacts', '__pycache__', '.venv*'))
            (home / 'cache').mkdir()
            cache = Path.home() / '.cache/uv'
            if cache.exists():
                (home / 'cache/uv').symlink_to(cache, target_is_directory=True)
            (home / 'config.yaml').write_text(json.dumps({
                'plugins': {'enabled': ['acedatacloud-media'], 'isolation': mode},
                'toolsets': ['acedatacloud-suno'],
            }))
            env = {k: v for k, v in os.environ.items() if k in {
                'PATH', 'HOME', 'USER', 'LANG', 'TMPDIR', 'DUCKWORK_RUNTIME_DIR'}}
            env.update(DUCKWORK_HOME=str(home), DUCKWORK_PYTHON=sys.executable,
                       PYTHONPATH=str(source), COLUMNS='180')
            run = subprocess.run([sys.executable, str(__file__), '--child', mode],
                                 env=env, cwd=source, capture_output=True, text=True, timeout=240)
            print(run.stdout)
            if run.returncode:
                print(run.stderr, file=sys.stderr)
                raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
