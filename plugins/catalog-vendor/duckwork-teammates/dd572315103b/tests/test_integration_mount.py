"""Actual pinned loader and lifecycle launch, with only child execution stubbed."""
import json
from types import SimpleNamespace

from conftest import PLUGIN_ROOT


def test_pinned_loader_registers_and_real_lifecycle_launches(monkeypatch, tmp_path):
    home = tmp_path / 'duckwork'
    home.mkdir(exist_ok=True)
    (home / 'plugins').mkdir()
    (home / 'plugins' / 'duckwork-teammates').symlink_to(PLUGIN_ROOT, target_is_directory=True)
    (home / 'config.yaml').write_text('plugins:\n  enabled: [duckwork-teammates]\n  entries:\n'
                                     '    duckwork-teammates:\n      settings:\n'
                                     '        teammates:\n          worker: {}\n')
    from duckwork_cli.plugins import PluginManager
    from agent.subagent_lifecycle import bind_subagent_parent
    from tools import delegate_tool
    from tools.registry import registry
    manager = PluginManager()
    manager.discover_and_load()
    try:
        assert 'teammates' in manager._plugin_commands
        names = {'teammates_roster','teammate_assign','teammate_check','teammate_message','teammate_stop'}
        assert names <= manager._plugin_tool_names
        loaded = manager._plugins['duckwork-teammates']
        assert not loaded.error
        skill = manager._plugin_skills['duckwork-teammates:teammates-report-problem']
        assert skill['path'].name == 'SKILL.md' and skill['description'] == 'Duckwork Teammates: report a bug or problem'
        assert loaded.module.__package__.startswith('duckwork_plugins.duckwork_teammates')
        command = manager._plugin_commands['teammates']['handler']
        text = command('')
        assert text.startswith('Teammates (1):') and '  worker - ' in text and 'This Duckwork build: steer=' in text
        constructions = []
        def build(**kwargs):
            constructions.append(kwargs)
            return SimpleNamespace(_subagent_id='stub-mount', provider='stub', model='stub-model')
        monkeypatch.setattr(delegate_tool, '_build_child_preserving_parent_tools', build)
        monkeypatch.setattr(delegate_tool, '_run_child_lifecycle',
                            lambda *args: {'status':'completed','summary':'done'})
        parent = SimpleNamespace(session_id='mount-session')
        with bind_subagent_parent(parent):
            assign = registry.get_entry('teammate_assign', scope=manager.scope_key).handler
            check = registry.get_entry('teammate_check', scope=manager.scope_key).handler
            result = json.loads(assign({'teammate':'worker','goal':'goal'}, session_id='mount-session'))
            assert result['ok'], result
            final = json.loads(check({'run_id':result['run_id'],'wait_seconds':5}, session_id='mount-session'))
        assert final['status'] == 'succeeded' and final['summary'] == 'done'
        assert len(constructions) == 1 and constructions[0]['role'] == 'leaf'
    finally:
        manager.unload()
