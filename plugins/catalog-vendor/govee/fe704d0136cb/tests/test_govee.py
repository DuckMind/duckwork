import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    spec = importlib.util.spec_from_file_location('govee_plugin', ROOT / '__init__.py')
    if spec is None or not Path(spec.origin).exists():
        raise AssertionError('Govee plugin has not been implemented')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, size):
        return self.body[:size]


class DiscoveryTests(unittest.TestCase):
    def test_discovery_uses_authenticated_current_api_and_filters_lights(self):
        g = load_plugin()
        seen = []
        def transport(request, timeout):
            seen.append(request)
            return Response({'code': 200, 'data': [
                {'sku': 'H6001', 'device': 'test-light', 'deviceName': 'Desk',
                 'type': 'devices.types.light', 'capabilities': []},
                {'sku': 'H7001', 'device': 'test-heater', 'type': 'devices.types.heater'},
            ]})
        client = g.GoveeClient(api_key='fake-test-key', transport=transport)
        devices = client.lights()
        self.assertEqual([d['deviceName'] for d in devices], ['Desk'])
        self.assertEqual(seen[0].full_url, 'https://openapi.api.govee.com/router/api/v1/user/devices')
        self.assertEqual(seen[0].get_header('Govee-api-key'), 'fake-test-key')
        self.assertEqual(seen[0].method, 'GET')


class ControlTests(unittest.TestCase):
    def test_power_validates_capability_sends_command_and_reads_back(self):
        g = load_plugin()
        calls = []
        light = {'sku': 'H6001', 'device': 'test-light', 'deviceName': 'Desk',
                 'type': 'devices.types.light', 'capabilities': [
                     {'type': 'devices.capabilities.on_off', 'instance': 'powerSwitch',
                      'parameters': {'dataType': 'ENUM', 'options': [{'value': 0}, {'value': 1}]}}]}
        def transport(request, timeout):
            body = json.loads(request.data) if request.data else None
            calls.append((request.full_url, body))
            if request.full_url.endswith('/user/devices'):
                return Response({'code': 200, 'data': [light]})
            if request.full_url.endswith('/device/control'):
                return Response({'code': 200, 'msg': 'success'})
            return Response({'code': 200, 'payload': {'capabilities': [
                {'type': 'devices.capabilities.on_off', 'instance': 'powerSwitch', 'state': {'value': 1}}]}})
        client = g.GoveeClient(api_key='fake-test-key', transport=transport, sleep=lambda _: None)
        result = client.control('Desk', 'power', True)
        self.assertTrue(result['verified'])
        command = next(body for url, body in calls if url.endswith('/device/control'))
        self.assertEqual(command['payload']['capability'], {
            'type': 'devices.capabilities.on_off', 'instance': 'powerSwitch', 'value': 1})
        import uuid
        uuid.UUID(command['requestId'])
        self.assertTrue(calls[-1][0].endswith('/device/state'))


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.g = load_plugin()
        self.light = {'sku': 'H6001', 'device': 'test-light', 'deviceName': 'Desk',
                      'type': 'devices.types.light', 'capabilities': [
            {'type': 'devices.capabilities.range', 'instance': 'brightness',
             'parameters': {'dataType': 'INTEGER', 'range': {'min': 1, 'max': 100}}},
            {'type': 'devices.capabilities.color_setting', 'instance': 'colorRgb',
             'parameters': {'dataType': 'INTEGER', 'range': {'min': 0, 'max': 16777215}}},
            {'type': 'devices.capabilities.color_setting', 'instance': 'colorTemperatureK',
             'parameters': {'dataType': 'INTEGER', 'range': {'min': 2000, 'max': 9000}}},
            {'type': 'devices.capabilities.dynamic_scene', 'instance': 'lightScene',
             'parameters': {'dataType': 'ENUM', 'options': []}},
        ]}
        self.calls = []
        self.last = None
        self.stale = False
        def transport(request, timeout):
            body = json.loads(request.data) if request.data else None
            self.calls.append((request.full_url, body))
            if request.full_url.endswith('/user/devices'):
                return Response({'code': 200, 'data': [self.light]})
            if request.full_url.endswith('/device/scenes'):
                return Response({'code': 200, 'payload': {'capabilities': [{
                    'type': 'devices.capabilities.dynamic_scene', 'instance': 'lightScene',
                    'parameters': {'dataType': 'ENUM', 'options': [
                        {'name': 'Aurora', 'value': {'paramId': 42, 'id': 7}}]}}]}})
            if request.full_url.endswith('/device/control'):
                self.last = body['payload']['capability']
                return Response({'code': 200})
            return Response({'code': 200, 'payload': {'capabilities': [{
                'type': self.last['type'], 'instance': self.last['instance'],
                'state': {'value': -1 if self.stale else self.last['value']}}]}})
        self.client = self.g.GoveeClient(api_key='fake-test-key', transport=transport, sleep=lambda _: None)

    def test_brightness_rgb_and_kelvin_use_advertised_capabilities(self):
        for action, value, expected in [('brightness', 55, 55), ('color', '#12AB34', 1223476),
                                        ('temperature', 2700, 2700)]:
            with self.subTest(action=action):
                self.assertTrue(self.client.control('Desk', action, value)['verified'])
                self.assertEqual(self.last['value'], expected)

    def test_dynamic_scene_preserves_structured_value(self):
        result = self.client.control('Desk', 'scene', 'Aurora')
        self.assertEqual(self.last['value'], {'paramId': 42, 'id': 7})
        self.assertTrue(result['verified'])

    def test_invalid_or_unsupported_values_never_send_control(self):
        for action, value in [('brightness', 0), ('brightness', True), ('brightness', 101),
                              ('temperature', 1900), ('color', '#GG0000'), ('scene', 'Nope'),
                              ('heater', 90), ('brightness', 2.5)]:
            with self.subTest(action=action, value=value):
                with self.assertRaises(ValueError):
                    self.client.control('Desk', action, value)
        self.assertFalse(any(url.endswith('/device/control') for url, _ in self.calls))

    def test_stale_state_is_not_reported_as_verified(self):
        self.stale = True
        self.assertFalse(self.client.control('Desk', 'brightness', 50)['verified'])

    def test_duplicate_names_are_rejected(self):
        with patch.object(self.client, 'lights', return_value=[self.light, dict(self.light, device='other')]):
            with self.assertRaises(ValueError):
                self.client.resolve('Desk')


class ErrorTests(unittest.TestCase):
    def test_api_auth_and_rate_limit_errors_are_sanitized(self):
        g = load_plugin()
        for code in (401, 429, 500):
            client = g.GoveeClient(api_key='fake-test-key', transport=lambda *a, **k: Response({
                'code': code, 'message': 'fake-test-key'}))
            with self.assertRaises(g.GoveeError) as caught:
                client.lights()
            self.assertNotIn('fake-test-key', str(caught.exception))

    def test_missing_api_code_is_not_treated_as_success(self):
        g = load_plugin()
        client = g.GoveeClient(api_key='fake-test-key', transport=lambda *a, **k: Response({'data': []}))
        with self.assertRaises(g.GoveeError):
            client.lights()


class SafetyTests(unittest.TestCase):
    def test_http_error_body_is_not_exposed(self):
        g = load_plugin()
        import io
        import urllib.error
        def transport(*args, **kwargs):
            raise urllib.error.HTTPError('https://example.invalid', 401, 'fake-test-key', {}, io.BytesIO(b'fake-test-key'))
        with self.assertRaises(g.GoveeError) as caught:
            g.GoveeClient(api_key='fake-test-key', transport=transport).lights()
        self.assertNotIn('fake-test-key', str(caught.exception))

    def test_redirect_refuses_to_forward_credentials(self):
        g = load_plugin()
        import urllib.request
        request = urllib.request.Request(g.BASE_URL, headers={'Govee-API-Key': 'fake-test-key'})
        with self.assertRaises(g.GoveeError):
            g.NoRedirect().redirect_request(request, None, 302, 'redirect', {}, 'https://example.invalid')

    def test_key_resolves_from_active_profile_scope(self):
        g = load_plugin()
        import types
        secret = types.ModuleType('agent.secret_scope')
        from unittest.mock import Mock
        secret.get_secret = Mock(return_value='fake-test-key')
        with patch.dict(sys.modules, {'agent': types.ModuleType('agent'), 'agent.secret_scope': secret}):
            client = g.GoveeClient(transport=lambda *a, **k: Response({'code': 200, 'data': []}))
            self.assertEqual(client.lights(), [])
        secret.get_secret.assert_called_once_with('GOVEE_API_KEY')

    def test_offline_state_is_never_verified_even_if_value_matches(self):
        g = load_plugin()
        client = g.GoveeClient(api_key='fake-test-key', sleep=lambda _: None)
        light = {'device': 'test-light', 'sku': 'H6001', 'capabilities': [{
            'type': 'devices.capabilities.range', 'instance': 'brightness',
            'parameters': {'range': {'min': 1, 'max': 100}}}]}
        state = {'capabilities': [
            {'type': 'devices.capabilities.online', 'instance': 'online', 'state': {'value': False}},
            {'type': 'devices.capabilities.range', 'instance': 'brightness', 'state': {'value': 50}}]}
        with patch.object(client, 'resolve', return_value=light), patch.object(client, 'request', return_value={'code': 200}), patch.object(client, 'state', return_value=state):
            self.assertFalse(client.control('test-light', 'brightness', 50)['verified'])


class RegistrationTests(unittest.TestCase):
    def test_plugin_registers_tool_and_skill_and_list_handler(self):
        g = load_plugin()
        from unittest.mock import Mock
        ctx = Mock()
        g.register(ctx)
        self.assertEqual(ctx.register_tool.call_args.kwargs['name'], 'govee_lights')
        self.assertEqual(ctx.register_skill.call_args.args[0], 'lights')
        with patch.object(g, 'GoveeClient') as factory:
            factory.return_value.lights.return_value = [{'device': 'test-light'}]
            result = json.loads(g.govee_lights({'action': 'list'}))
        self.assertTrue(result['ok'])
        self.assertEqual(result['lights'][0]['device'], 'test-light')


if __name__ == '__main__':
    unittest.main()
