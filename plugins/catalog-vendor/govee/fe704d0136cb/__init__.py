"""Capability-aware Govee cloud tools. No dependency installation required."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE_URL = 'https://openapi.api.govee.com/router/api/v1'
ACTIONS = {
    'power': ('devices.capabilities.on_off', 'powerSwitch'),
    'brightness': ('devices.capabilities.range', 'brightness'),
    'color': ('devices.capabilities.color_setting', 'colorRgb'),
    'temperature': ('devices.capabilities.color_setting', 'colorTemperatureK'),
    'scene': ('devices.capabilities.dynamic_scene', 'lightScene'),
}


class GoveeError(ValueError):
    """A sanitized API failure that never includes response bodies or credentials."""


def error_for_code(code):
    if code in (401, 403):
        return GoveeError('Govee rejected the API key. Replace GOVEE_API_KEY through secure input.')
    if code == 429:
        return GoveeError('Govee rate limit reached. Wait before trying again; do not retry commands automatically.')
    return GoveeError(f'Govee request failed (code {code if isinstance(code, (int, str)) and str(code).isdigit() else "unknown"}).')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise GoveeError('Govee returned a redirect; refused to forward the API key.')


class GoveeClient:
    def __init__(self, api_key=None, transport=None, sleep=time.sleep):
        if api_key is None:
            from agent.secret_scope import get_secret
            api_key = get_secret('GOVEE_API_KEY')
        if not api_key:
            raise GoveeError('GOVEE_API_KEY is missing. Request it through secure input.')
        self._key = api_key
        self._transport = transport or urllib.request.build_opener(NoRedirect()).open
        self._sleep = sleep

    def request(self, endpoint, payload=None):
        if endpoint not in ('/user/devices', '/device/state', '/device/scenes', '/device/control'):
            raise ValueError('Unsupported Govee endpoint')
        request = urllib.request.Request(
            BASE_URL + endpoint,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Govee-API-Key': self._key, 'Content-Type': 'application/json'},
            method='POST' if payload is not None else 'GET',
        )
        try:
            with self._transport(request, timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise GoveeError('Govee response exceeded the size limit.')
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise error_for_code(exc.code) from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise GoveeError('Govee network request failed. A control may have been delivered; check state before retrying.') from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GoveeError('Govee returned invalid JSON.') from None
        if not isinstance(result, dict) or str(result.get('code')) != '200':
            raise error_for_code(result.get('code') if isinstance(result, dict) else None)
        return result

    def lights(self):
        data = self.request('/user/devices').get('data')
        if not isinstance(data, list):
            raise GoveeError('Govee device list was missing.')
        return [d for d in data if isinstance(d, dict) and d.get('type') == 'devices.types.light']

    def resolve(self, target):
        if not isinstance(target, str) or not target or len(target) > 256:
            raise ValueError('Provide a light name or exact device ID, at most 256 characters.')
        lights = self.lights()
        matches = [d for d in lights if d.get('device') == target]
        if not matches:
            matches = [d for d in lights if d.get('deviceName', '').casefold() == target.casefold()]
        if len(matches) != 1:
            raise ValueError('Light not found or name is ambiguous; use an exact device ID from list.')
        return matches[0]

    def device_request(self, endpoint, light):
        result = self.request(endpoint, {
            'requestId': str(uuid.uuid4()),
            'payload': {'sku': light['sku'], 'device': light['device']},
        }).get('payload')
        if not isinstance(result, dict):
            raise GoveeError('Govee device response was missing its payload.')
        return result

    def state(self, light):
        return self.device_request('/device/state', light)

    def scenes(self, light):
        static = [c for c in light.get('capabilities', [])
                  if (c.get('type'), c.get('instance')) == ACTIONS['scene']]
        dynamic = self.device_request('/device/scenes', light).get('capabilities', [])
        options = []
        for c in [*static, *dynamic]:
            if (c.get('type'), c.get('instance')) == ACTIONS['scene']:
                for option in c.get('parameters', {}).get('options', []):
                    if option not in options:
                        options.append(option)
        return options

    def control(self, target, action, value):
        if action not in ACTIONS:
            raise ValueError('Unsupported light action')
        light = self.resolve(target)
        cap_type, instance = ACTIONS[action]
        matches = [c for c in light.get('capabilities', [])
                   if (c.get('type'), c.get('instance')) == (cap_type, instance)]
        if len(matches) != 1:
            raise ValueError(f'Light does not support {instance}')
        capability = matches[0]
        parameters = capability.get('parameters', {})
        if action == 'power':
            if type(value) is not bool:
                raise ValueError('power requires a boolean value')
            wire_value = int(value)
        elif action == 'color':
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                raise ValueError('color requires #RRGGBB')
            wire_value = int(value[1:], 16)
        elif action == 'scene':
            if not isinstance(value, str) or len(value) > 256:
                raise ValueError('scene requires a scene name')
            options = self.scenes(light)
            matching = [o for o in options if o.get('name', '').casefold() == value.casefold()]
            if len(matching) != 1:
                raise ValueError('Scene missing or ambiguous; list scenes first.')
            wire_value = matching[0]['value']
        else:
            if type(value) is not int:
                raise ValueError(f'{action} requires an integer')
            wire_value = value
        if action in ('brightness', 'color', 'temperature'):
            bounds = parameters.get('range', {})
            if 'min' not in bounds or 'max' not in bounds:
                raise ValueError('Device did not advertise a valid range; refused control.')
            if not bounds['min'] <= wire_value <= bounds['max']:
                raise ValueError(f'{action} must be between {bounds["min"]} and {bounds["max"]}')
        if action == 'power' and wire_value not in [o.get('value') for o in parameters.get('options', [])]:
            raise ValueError('Device did not advertise this power value.')
        self.request('/device/control', {
            'requestId': str(uuid.uuid4()),
            'payload': {'sku': light['sku'], 'device': light['device'], 'capability': {
                'type': cap_type, 'instance': instance, 'value': wire_value}},
        })
        result = {'ok': True, 'accepted': True, 'verified': False,
                  'device': light['device'], 'deviceName': light.get('deviceName'),
                  'requested': {'type': cap_type, 'instance': instance, 'value': wire_value}}
        # The cloud may report stale state briefly. Two reads, spaced for the 30/min limit.
        for _ in range(2):
            self._sleep(2.1)
            try:
                state = self.state(light)
            except GoveeError as exc:
                result['verification_error'] = str(exc)
                break
            result['state'] = state
            capabilities = state.get('capabilities', [])
            offline = any(c.get('instance') == 'online' and
                          c.get('state', {}).get('value') is False for c in capabilities)
            result['verified'] = not offline and any(
                (c.get('type'), c.get('instance')) == (cap_type, instance)
                and c.get('state', {}).get('value') == wire_value
                for c in capabilities)
            if result['verified']:
                break
        if not result['verified']:
            result['note'] = 'Command accepted, but state read-back did not confirm it. Do not claim the light changed.'
        return result


DESCRIPTION = (
    'Discover and control Govee lights using the saved GOVEE_API_KEY. '
    'Actions: list, state, scenes, power (boolean), brightness (integer percent), '
    'color (#RRGGBB), temperature (integer Kelvin), scene (exact scene name). '
    'Use a light name or exact device ID from list. Change only lights the person requested. '
    'Read-back is automatic: accepted does not mean verified. Read govee:lights for details.'
)
SCHEMA = {
    'name': 'govee_lights', 'description': DESCRIPTION,
    'parameters': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'action': {'type': 'string', 'enum': ['list', 'state', 'scenes', *ACTIONS]},
            'device': {'type': 'string', 'description': 'Exact device ID or unambiguous light name.'},
            'value': {'anyOf': [{'type': 'boolean'}, {'type': 'integer'}, {'type': 'string'}]},
        },
        'required': ['action'],
    },
}


def govee_lights(args=None, **kwargs):
    params = dict(args or {})
    params.update(kwargs)
    try:
        action = params.get('action')
        if action not in ('list', 'state', 'scenes', *ACTIONS):
            raise ValueError('Unknown action')
        client = GoveeClient()
        if action == 'list':
            result = {'ok': True, 'lights': client.lights()}
        elif action in ('state', 'scenes'):
            light = client.resolve(params.get('device'))
            result = {'ok': True, 'device': light['device'], 'deviceName': light.get('deviceName'),
                      action: client.state(light) if action == 'state' else client.scenes(light)}
        else:
            result = client.control(params.get('device'), action, params.get('value'))
        return json.dumps(result)
    except (ValueError, KeyError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Unexpected Govee response or invalid arguments.'
        return json.dumps({'ok': False, 'error': message})


def register(ctx):
    ctx.register_tool(name='govee_lights', toolset='govee', schema=SCHEMA,
                      handler=govee_lights, description=DESCRIPTION, emoji='💡')
    ctx.register_skill('lights', Path(__file__).parent / 'skills/lights/SKILL.md',
                       description='Use when discovering or controlling Govee lights.')
