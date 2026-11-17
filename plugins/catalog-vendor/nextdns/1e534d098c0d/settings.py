"""Shared settings for the NextDNS plugin.

Resolution order is file, then environment, then default. The dashboard writes
the file; environment variables remain the fallback for headless installs.

The API key is stored in the settings file when set from the dashboard. That
file lives in DUCKWORK_HOME alongside other agent state, so it is written 0600
and the key is never returned to the browser - only whether one is present.
"""

import json
import os
import threading
from typing import Any, Dict

SETTINGS_FILENAME = "nextdns_settings.json"

FIELDS = {
    "api_key": ("NEXTDNS_API_KEY", ""),
    "profile_id": ("NEXTDNS_PROFILE_ID", ""),
}

SECRET_FIELDS = ("api_key",)
_lock = threading.Lock()


def path() -> str:
    home = (os.environ.get("DUCKWORK_HOME") or "").strip() or os.path.expanduser("~/.duckwork")
    return os.path.join(home, SETTINGS_FILENAME)


def _read_file() -> Dict[str, Any]:
    try:
        p = path()
        if os.path.exists(p):
            with open(p) as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        pass
    return {}


def load() -> Dict[str, Any]:
    stored = _read_file()
    out: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    for key, (env_var, default) in FIELDS.items():
        if key in stored and str(stored[key]).strip():
            out[key] = str(stored[key]).strip()
            sources[key] = "settings"
            continue
        raw = (os.environ.get(env_var) or "").strip()
        if raw:
            out[key] = raw
            sources[key] = "env"
            continue
        out[key] = default
        sources[key] = "default"
    out["_sources"] = sources
    return out


def public() -> Dict[str, Any]:
    """Settings safe to send to a browser: secrets reduced to a presence flag."""
    data = load()
    sources = data.pop("_sources", {})
    out = {k: v for k, v in data.items() if k not in SECRET_FIELDS}
    for k in SECRET_FIELDS:
        out[k + "_set"] = bool(data.get(k))
    return {"settings": out, "sources": sources}


def save(patch: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        stored = _read_file()
        for key, value in (patch or {}).items():
            if key not in FIELDS:
                continue
            if value is None or not str(value).strip():
                stored.pop(key, None)
            else:
                stored[key] = str(value).strip()
        p = path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(stored, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    return public()
