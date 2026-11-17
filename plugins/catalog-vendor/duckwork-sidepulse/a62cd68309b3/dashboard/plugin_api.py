"""Authenticated Desktop activation, independent of Duckwork lifecycle internals.

The Desktop SDK supplies the focused session's owning profile and durable ID.
Only status metadata is accepted; no messages, prompts, tools, or arbitrary paths.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import yaml

# Dashboard API files load as standalone modules. Give OUR package a private
# namespace to reuse settings/translation without modifying sys.path or Duckwork.
_ROOT = Path(__file__).resolve().parents[1]
_NAME = '_sidepulse_desktop_backend'
if _NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_NAME, _ROOT/'__init__.py', submodule_search_locations=[str(_ROOT)])
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_NAME] = _module
    try:
        _spec.loader.exec_module(_module)
    except Exception:
        sys.modules.pop(_NAME, None)
        raise
_plugin = sys.modules[_NAME]
router = APIRouter()


class Activation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    session_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$')
    runtime_session_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$')
    profile: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')
    running: bool
    reason: Literal['desktop_focus']


def _authorize(request: Request) -> None:
    # Same session-token / OAuth gate as sensitive built-in REST endpoints.
    from duckwork_cli.web_server import _require_token
    _require_token(request)


def _profile_dir(name: str) -> Path:
    from duckwork_cli.profiles import get_profile_dir
    return get_profile_dir(name)


def _settings(profile: str):
    try:
        raw = yaml.safe_load((_profile_dir(profile)/'config.yaml').read_text())
        plugins = raw.get('plugins', {})
        if 'duckwork-sidepulse' not in plugins.get('enabled', []) or 'duckwork-sidepulse' in plugins.get('disabled', []):
            raise ValueError('disabled')
        entry = plugins.get('entries', {}).get('duckwork-sidepulse', {})
        if entry.get('enabled') is False:
            raise ValueError('disabled entry')
        settings, legacy = entry.get('settings', {}), entry.get('config', {})
        if not isinstance(settings, dict) or not isinstance(legacy, dict):
            raise ValueError('invalid settings')
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
        raise HTTPException(403, 'SidePulse is not enabled for this local profile') from None

    class Context:
        profile_name = profile
        def get_config(self, key, default=None):
            return settings.get(key, legacy.get(key, default))
    return _plugin._settings_from_context(Context())


@router.get('/health')
def health(request: Request):
    _authorize(request)
    return {'ok': True, 'version': '0.2.0-beta.1', 'activation_source': 'desktop-sdk', 'requires_core_hook': False}


@router.post('/activate')
async def activate(request: Request):
    _authorize(request)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 4096:
            raise HTTPException(413, 'Activation payload too large')
    try:
        activation = Activation.model_validate(json.loads(body))
    except (ValueError, ValidationError):
        # Do not echo invalid/sensitive inputs in validation errors.
        raise HTTPException(422, 'Invalid activation metadata') from None
    return await run_in_threadpool(_deliver, activation)


def _deliver(activation: Activation):
    settings = _settings(activation.profile)
    previous = _plugin.recover_session_mode(settings, activation.session_id)
    # Focus alone cannot resolve an outstanding user question/approval.
    mode = 'waiting_for_input' if previous == 'waiting_for_input' else ('working' if activation.running else 'idle_ready')
    result = _plugin.emit_hook('desktop_session_activate', {
        'session_id': activation.session_id,
        'platform': 'desktop',
        'activation_mode': mode,
    }, settings)
    return {'ok': result.event is not None, 'logged': result.logged, 'delivered': result.delivered}
