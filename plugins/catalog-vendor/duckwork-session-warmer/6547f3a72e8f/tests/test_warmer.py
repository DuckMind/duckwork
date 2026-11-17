import copy
import importlib.util
import json
import pathlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('warmer', ROOT / 'warmer.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REQUEST = {'model': 'test-model', 'messages': [
    {'role': 'system', 'content': 'Stable instructions'},
    {'role': 'user', 'content': 'hello'}],
    'tools': [{'type': 'function', 'function': {'name': 'dangerous_tool',
              'parameters': {'type': 'object', 'properties': {}}}}], 'stream': True}


class Tests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.config = dict(enabled=True, base_url='http://127.0.0.1:12345/v1',
                           models=['test-model'], interval_seconds=30,
                           idle_window_seconds=120, max_requests=2)
        self.calls = []
        self.w = mod.Warmer(lambda: self.config, lambda: self.now,
                            lambda *args: self.calls.append(args) or {'cached_tokens': 42})
        self.w.thread = True  # Deterministic clock tests; scheduler separately tested.
        self.addCleanup(self.w.command, 'stop')

    def arm(self, sid='a'):
        self.w.capture(copy.deepcopy(REQUEST), sid, self.config['base_url'])
        self.w.idle(sid, assistant_response='Hello')
        self.w.remove(sid, completed=True)

    def test_default_off(self):
        self.config = {}
        self.w.capture(REQUEST, 'a', 'http://127.0.0.1/v1')
        self.assertFalse(self.w.sessions)

    def test_timing_budget_and_expiry(self):
        self.arm()
        for t in [29, 30, 31, 59, 60, 90, 150]:
            self.now = t
            self.w.tick()
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(self.w.sessions)
        self.assertEqual(self.w.metrics['cached_tokens'], 84)

    def test_window_not_extended_by_warm(self):
        self.config['max_requests'] = 30
        self.arm()
        for t in [30, 60, 90, 120]:
            self.now = t
            self.w.tick()
        self.assertEqual(len(self.calls), 3)

    def test_no_mutation_exact_prefix_and_tool_safety(self):
        original = copy.deepcopy(REQUEST)
        self.w.capture(REQUEST, 'a', self.config['base_url'])
        self.w.idle('a', assistant_response='Hello')
        self.now = 30
        self.w.tick()
        body = json.loads(self.calls[0][1])
        self.assertEqual(REQUEST, original)
        self.assertEqual(body['messages'][:-2], REQUEST['messages'])
        self.assertEqual(body['tools'], REQUEST['tools'])
        self.assertEqual(body['messages'][-2]['role'], 'assistant')
        self.assertEqual(body['tool_choice'], 'none')
        self.assertEqual(body['max_tokens'], 1)
        self.assertFalse(body['stream'])
        self.assertFalse(body['store'])

    def test_busy_and_failed_turns_do_not_warm(self):
        self.arm()
        self.w.busy('a')
        self.now = 30
        self.w.tick()
        self.assertEqual(self.calls, [])
        self.arm()
        self.w.remove('a', completed=False, interrupted=True)
        self.now = 60
        self.w.tick()
        self.assertEqual(self.calls, [])

    def test_capture_is_not_idle(self):
        self.w.capture(REQUEST, 'a', self.config['base_url'])
        self.now = 30
        self.w.tick()
        self.assertEqual(self.calls, [])

    def test_missing_reply_and_session_id(self):
        self.w.capture(REQUEST, '', self.config['base_url'])
        self.assertFalse(self.w.sessions)
        self.w.capture(REQUEST, 'a', self.config['base_url'])
        self.w.idle('a')
        self.assertFalse(self.w.sessions)

    def test_endpoint_and_model_mismatch(self):
        self.w.capture(REQUEST, 'a', 'https://other.invalid/v1')
        self.w.capture(dict(REQUEST, model='other'), 'b', self.config['base_url'])
        self.assertFalse(self.w.sessions)

    def test_config_change_and_disable_drop_snapshot(self):
        self.arm()
        self.config['models'] = ['new-model']
        self.now = 30
        self.w.tick()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.w.sessions)

    def test_stop(self):
        self.arm()
        status = json.loads(self.w.command('stop'))
        self.now = 30
        self.w.tick()
        self.assertTrue(status['stopped'])
        self.assertEqual(self.calls, [])
        self.assertNotIn('Stable instructions', json.dumps(status))

    def test_error_circuit_breaker(self):
        def fail(*args):
            raise RuntimeError('private provider error text')
        self.w.transport = fail
        self.arm()
        self.now = 30
        self.w.tick()
        self.now = 60
        self.w.tick()
        self.assertEqual(self.w.metrics['attempts'], 1)
        self.assertEqual(self.w.metrics['errors'], 1)
        self.assertNotIn('private', self.w.command())

    def test_session_capacity_and_separation(self):
        self.config['max_sessions'] = 1
        self.arm('a')
        self.arm('b')
        self.assertEqual(set(self.w.sessions), {'a'})

    def test_payload_capacity(self):
        self.config['max_payload_bytes'] = 1024
        request = copy.deepcopy(REQUEST)
        request['messages'][0]['content'] = 'x' * 2000
        self.w.capture(request, 'a', self.config['base_url'])
        self.assertFalse(self.w.sessions)

    def test_unsupported_fields_and_server_tools(self):
        for changes in [{'input': []}, {'extra_body': {}}, {'tools': [{'type': 'web_search'}]},
                        {'messages': [{'role': 'user', 'content': [{'type': 'image_url'}]}]}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                mod.payload(dict(REQUEST, **changes))

    def test_invalid_config(self):
        for changes in [{'interval_seconds': float('nan')}, {'max_requests': 1.5},
                        {'max_sessions': True}, {'models': []}, {'interval_seconds': 1}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                mod.settings(dict(self.config, **changes))

    def test_endpoint_security(self):
        for url in ['http://example.com/v1', 'https://user:pass@example.com/v1',
                    'https://example.com/v1?key=x', 'file:///tmp/foo']:
            with self.assertRaises(ValueError):
                mod.endpoint(url)
        self.assertEqual(mod.endpoint('http://[::1]:123/v1/'), 'http://[::1]:123/v1')

    def test_new_turn_during_inflight_does_not_restore_snapshot(self):
        self.arm()
        def send(*args):
            self.w.busy('a')
            return {}
        self.w.transport = send
        self.now = 30
        self.w.tick()
        self.assertFalse(self.w.sessions)

    def test_real_http_scheduler_and_redirect_refusal(self):
        received = []
        event = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                if self.path.startswith('/redirect'):
                    self.send_response(307)
                    self.send_header('Location', '/v1/chat/completions')
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'choices': [{'message': {'content': 'OK',
                    'tool_calls': [{'function': {'name': 'dangerous_tool'}}]}}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 1,
                              'prompt_tokens_details': {'cached_tokens': 80}}}).encode())
                event.set()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.config['base_url'] = f'http://127.0.0.1:{server.server_port}/v1'
        self.w.transport = mod.send
        self.w.thread = None
        self.arm()
        self.now = 30
        self.assertTrue(event.wait(5), 'real background scheduler did not POST')
        self.assertEqual(received[0]['tool_choice'], 'none')
        with self.assertRaises(Exception):
            mod.send(f'http://127.0.0.1:{server.server_port}/redirect', b'{}', 2)
        self.assertEqual(len(received), 2)  # Redirect not followed.


if __name__ == '__main__':
    unittest.main()
