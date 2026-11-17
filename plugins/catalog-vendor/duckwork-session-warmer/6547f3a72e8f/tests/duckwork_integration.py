"""Run with an installed Duckwork interpreter and upstream checkout on PYTHONPATH.
Real PluginManager, PluginContext, config loading, hooks, middleware and unload.
No cloud credentials, model downloads or live profile modifications.
"""
import copy
import json
import pathlib
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import yaml
from duckwork_cli.plugins import PluginManager
from duckwork_cli.plugins_manifest import PluginManifest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAME = 'duckwork-session-warmer'
REQUEST = {'model': 'test-model', 'messages': [{'role': 'user', 'content': 'hello'}]}

with tempfile.TemporaryDirectory(prefix='duckwork-warming-integration-') as tmp:
    managers = []
    for profile in ['A', 'B']:
        home = pathlib.Path(tmp) / profile
        home.mkdir()
        config = {'plugins': {'enabled': [NAME], 'entries': {NAME: {'settings': {'warming': {
            'enabled': profile == 'A', 'base_url': 'http://127.0.0.1:12345/v1',
            'models': ['test-model']}}}}}}
        (home / 'config.yaml').write_text(yaml.safe_dump(config))
        manager = PluginManager(scope_key=str(home))
        manager._load_plugin(PluginManifest(name=NAME, path=str(ROOT), source='user'))
        assert manager._plugins[NAME].enabled, manager._plugins[NAME]
        managers.append(manager)
    a, b = managers
    original = copy.deepcopy(REQUEST)
    for manager in [a, b, a]:
        manager.invoke_hook('pre_llm_call', session_id='same-id')
        result = manager.invoke_middleware('llm_request', request=REQUEST,
            session_id='same-id', base_url='http://127.0.0.1:12345/v1')
        assert result == []
        manager.invoke_hook('post_llm_call', session_id='same-id', assistant_response='Hello')
        manager.invoke_hook('on_session_end', session_id='same-id', completed=True,
                            failed=False, interrupted=False)
        status = json.loads(manager._plugin_commands['warming']['handler']('status'))
        assert status['sessions'] == (1 if manager is a else 0), status
    assert REQUEST == original
    # Real registered background worker -> real local HTTP socket. Fixture, not an LLM.
    received = []
    arrived = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"choices":[{"message":{"content":"OK"}}],"usage":{}}')
            arrived.set()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        cfg_path = pathlib.Path(tmp) / 'A' / 'config.yaml'
        cfg = yaml.safe_load(cfg_path.read_text())
        url = f'http://127.0.0.1:{server.server_port}/v1'
        cfg['plugins']['entries'][NAME]['settings']['warming'].update(
            base_url=url, interval_seconds=30, max_requests=1)
        cfg_path.write_text(yaml.safe_dump(cfg))
        a.invoke_hook('pre_llm_call', session_id='http-session')
        a.invoke_middleware('llm_request', request=REQUEST, session_id='http-session', base_url=url)
        a.invoke_hook('post_llm_call', session_id='http-session', assistant_response='Hello')
        a.invoke_hook('on_session_end', session_id='http-session', completed=True)
        assert arrived.wait(36), 'real Duckwork worker did not send warming POST'
        assert received[0]['messages'][:1] == REQUEST['messages']
        assert received[0]['max_tokens'] == 1
        print('PASS: real Duckwork registered worker -> local HTTP POST after 30-second idle interval')
    finally:
        server.shutdown()
        server.server_close()
    callback = a._plugin_commands['warming']['handler']
    a.unload(NAME)
    assert json.loads(callback('status'))['stopped']
    assert not a._middleware.get('llm_request')
    b.unload(NAME)
    print('PASS: real Duckwork A → B → A configuration isolation, lifecycle, unchanged request, unload cleanup')
