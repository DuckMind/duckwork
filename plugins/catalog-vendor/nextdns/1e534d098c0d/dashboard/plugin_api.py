"""Backend for the NextDNS dashboard tab.

Mounted at /api/plugins/nextdns/ by the Duckwork dashboard.
"""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict

try:
    from fastapi import APIRouter, Body
except Exception:  # Allows import without the dashboard dependencies present.
    class APIRouter:  # type: ignore
        def get(self, *_a, **_k):
            return lambda fn: fn

        def post(self, *_a, **_k):
            return lambda fn: fn

    def Body(default=None, **_k):  # type: ignore
        return default


router = APIRouter()

# Every Duckwork plugin's dashboard tab is mounted this same way, sharing one
# Python process -- so a plain `import settings`/`import tools` (relying on
# sys.path order for isolation) collides with any other plugin's same-named
# file via the shared sys.modules cache. Whichever plugin happens to import
# the bare name "settings" first "wins" it process-wide; every later `import
# settings`, from ANY plugin, silently gets that same cached module back
# regardless of sys.path. Confirmed live: this is why the Unraid dashboard tab
# was reading this plugin's own settings.py instead of its own.
#
# tools.py's own `from . import settings` falls back to the same bare import
# when there's no real package context (exactly the case here), so fixing
# only this file's imports isn't enough -- this plugin's own directory is
# loaded as a genuine (synthetic) package instead, under a globally-unique
# name, so every `from . import x` inside it resolves normally.
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_PKG_NAME = "duckwork_nextdns_plugin_pkg"

if _PKG_NAME not in sys.modules:
    _pkg = types.ModuleType(_PKG_NAME)
    _pkg.__path__ = [str(_PLUGIN_DIR)]
    sys.modules[_PKG_NAME] = _pkg

try:
    _settings = importlib.import_module(f"{_PKG_NAME}.settings")
    _tools = importlib.import_module(f"{_PKG_NAME}.tools")
except Exception:  # noqa: BLE001
    _settings = None
    _tools = None


@router.get("/settings")
def get_settings() -> Dict[str, Any]:
    """Current settings. The API key is never returned, only whether it is set."""
    if _settings is None:
        return {"ok": False, "error": "settings module unavailable"}
    return {"ok": True, **_settings.public()}


@router.post("/settings")
def post_settings(patch: Dict[str, Any] = Body(default=None)) -> Dict[str, Any]:
    if _settings is None:
        return {"ok": False, "error": "settings module unavailable"}
    if not isinstance(patch, dict):
        return {"ok": False, "error": "expected a JSON object"}
    try:
        return {"ok": True, **_settings.save(patch)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/profiles")
def get_profiles() -> Dict[str, Any]:
    """Profiles the key can see, so the id can be picked rather than typed."""
    if _tools is None:
        return {"ok": False, "error": "tools module unavailable"}
    body = _tools._get("/profiles")
    if "error" in body:
        return {"ok": False, "error": body["error"]}
    return {"ok": True, "profiles": [
        {"id": p.get("id"), "name": p.get("name")} for p in (body.get("data") or [])
    ]}


@router.get("/test")
def test_connection() -> Dict[str, Any]:
    """Verify the key and profile actually work, and report logging state."""
    if _tools is None:
        return {"ok": False, "error": "tools module unavailable"}
    try:
        result = json.loads(_tools.nextdns_profile({}))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if result.get("error"):
        return {"ok": False, "error": result["error"]}
    if result.get("profiles") is not None:
        return {"ok": False, "error": "No profile selected", "profiles": result["profiles"]}
    return {"ok": True, "profile": result}


@router.get("/recent")
def recent_blocked() -> Dict[str, Any]:
    """A small sample of recent blocks, to confirm data is flowing."""
    if _tools is None:
        return {"ok": False, "error": "tools module unavailable"}
    try:
        result = json.loads(_tools.nextdns_blocked({"limit": 10}))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if result.get("error"):
        return {"ok": False, "error": result["error"]}
    return {"ok": True, "logs": (result.get("logs") or [])[:10]}
