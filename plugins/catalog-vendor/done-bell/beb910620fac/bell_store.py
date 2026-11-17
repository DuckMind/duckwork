"""Done Bell settings and recent events under plugin-data."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ID = "done-bell"
MAX_EVENTS = 20

CLI_PLATFORMS = {"cli", "tui", "terminal", ""}

DEFAULT_SETTINGS: dict[str, bool] = {
    "muted": False,
    "sound": True,
    "os_notify": True,
    "in_app": False,
    "needs_you": True,
}

_lock = threading.Lock()


def data_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore

        return plugin_data_dir(PLUGIN_ID)
    except Exception:
        home = Path(os.environ.get("DUCKWORK_HOME") or (Path.home() / ".duckwork"))
        path = home / "plugin-data" / PLUGIN_ID
        path.mkdir(parents=True, exist_ok=True)
        return path


def state_path() -> Path:
    return data_dir() / "bell.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_state() -> dict[str, Any]:
    return {
        "settings": dict(DEFAULT_SETTINGS),
        "needs_you": False,
        "needs_you_at": "",
        "events": [],
    }


def _normalize_settings(raw: Any) -> dict[str, bool]:
    out = dict(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        for key in DEFAULT_SETTINGS:
            if key in raw:
                out[key] = bool(raw[key])
    return out


def _normalize_event(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "").strip()[:32]
    if kind not in {"done", "interrupted", "needs_you", "acked"}:
        return None
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:10]),
        "kind": kind,
        "at": str(raw.get("at") or now_iso())[:64],
        "session_id": str(raw.get("session_id") or "")[:80],
        "platform": str(raw.get("platform") or "")[:32],
        "detail": str(raw.get("detail") or "")[:120],
    }


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()
    if not isinstance(data, dict):
        return _empty_state()
    events = []
    for item in data.get("events") or []:
        event = _normalize_event(item)
        if event:
            events.append(event)
    return {
        "settings": _normalize_settings(data.get("settings")),
        "needs_you": bool(data.get("needs_you")),
        "needs_you_at": str(data.get("needs_you_at") or "")[:64],
        "events": events[-MAX_EVENTS:],
    }


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(state, ensure_ascii=False, indent=2)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(blob, encoding="utf-8")
    tmp.replace(path)


def get_settings() -> dict[str, bool]:
    with _lock:
        return dict(load_state()["settings"])


def patch_settings(patch: dict[str, Any]) -> dict[str, bool]:
    with _lock:
        state = load_state()
        settings = dict(state["settings"])
        for key in DEFAULT_SETTINGS:
            if key in patch and patch[key] is not None:
                settings[key] = bool(patch[key])
        state["settings"] = settings
        save_state(state)
        return dict(settings)


def list_events() -> list[dict[str, str]]:
    with _lock:
        return list(load_state()["events"])


def snapshot() -> dict[str, Any]:
    with _lock:
        state = load_state()
        return {
            "ok": True,
            "settings": dict(state["settings"]),
            "needs_you": bool(state["needs_you"]),
            "needs_you_at": state["needs_you_at"],
            "events": list(state["events"]),
        }


def record_event(
    kind: str,
    *,
    session_id: str = "",
    platform: str = "",
    detail: str = "",
    needs_you: bool | None = None,
) -> dict[str, str]:
    event = {
        "id": uuid.uuid4().hex[:10],
        "kind": kind,
        "at": now_iso(),
        "session_id": (session_id or "")[:80],
        "platform": (platform or "")[:32],
        "detail": (detail or "")[:120],
    }
    with _lock:
        state = load_state()
        events = list(state["events"])
        events.append(event)
        state["events"] = events[-MAX_EVENTS:]
        if needs_you is True:
            state["needs_you"] = True
            state["needs_you_at"] = event["at"]
        elif needs_you is False:
            state["needs_you"] = False
            state["needs_you_at"] = ""
        save_state(state)
    return event


def clear_needs_you() -> None:
    with _lock:
        state = load_state()
        if not state["needs_you"]:
            return
        state["needs_you"] = False
        state["needs_you_at"] = ""
        save_state(state)


def to_markdown(state: dict[str, Any] | None = None) -> str:
    snap = state or snapshot()
    settings = snap.get("settings") or {}
    muted = "on (muted)" if settings.get("muted") else "on"
    lines = [
        f"Done Bell is {muted}.",
        f"Waiting for approval: {'yes' if snap.get('needs_you') else 'no'}.",
    ]
    events = snap.get("events") or []
    if not events:
        lines.append("No turn events yet.")
        return "\n".join(lines)
    lines.append("Recent:")
    for event in reversed(events[-8:]):
        lines.append(f"- {event.get('kind')} ({event.get('at', '')[:19]})")
    return "\n".join(lines)


def should_os_notify_cli(platform_name: str) -> bool:
    settings = get_settings()
    if settings.get("muted") or not settings.get("os_notify"):
        return False
    key = (platform_name or "").strip().lower()
    return key in CLI_PLATFORMS


def ring_cli(title: str, body: str, *, platform_name: str = "") -> None:
    if os.environ.get("DONE_BELL_NO_OS") == "1":
        return
    if not should_os_notify_cli(platform_name):
        return
    settings = get_settings()
    if settings.get("sound"):
        _beep()
    threading.Thread(target=_os_toast, args=(title, body), daemon=True).start()


def _beep() -> None:
    try:
        if sys.platform == "win32":
            import winsound

            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            return
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        return


def _os_toast(title: str, body: str) -> None:
    try:
        system = platform.system()
        if system == "Windows":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "$n = New-Object System.Windows.Forms.NotifyIcon; "
                "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                "$n.Visible = $true; "
                f"$n.ShowBalloonTip(4000, '{_ps(title)}', '{_ps(body)}', "
                "[System.Windows.Forms.ToolTipIcon]::Info); "
                "Start-Sleep -Seconds 5; $n.Dispose()"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        if system == "Darwin":
            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    f'display notification "{_osa(body)}" with title "{_osa(title)}"',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        subprocess.Popen(
            ["notify-send", "--app-name=Duckwork", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return


def _ps(text: str) -> str:
    return (text or "").replace("'", "''")[:80]


def _osa(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')[:80]
