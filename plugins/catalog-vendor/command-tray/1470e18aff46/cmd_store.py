"""Durable session shell-command list for command-tray."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ID = "command-tray"
MAX_ITEMS = 40
MAX_COMMAND = 500
MAX_PREVIEW = 160
MAX_WORKDIR = 300

WATCH_TOOLS = {"terminal"}

_SECRET_RES = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|authorization)\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
)


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
    return data_dir() / "state.json"


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return {"items": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": []}
    if not isinstance(raw, dict):
        return {"items": []}
    items = raw.get("items")
    if not isinstance(items, list):
        raw["items"] = []
    return raw


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(text: str) -> str:
    out = text or ""
    for pat in _SECRET_RES:
        out = pat.sub("[redacted]", out)
    return out


def parse_tool_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if not isinstance(result, str) or not result.strip():
        return {}
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        return {"output": result}
    return parsed if isinstance(parsed, dict) else {"output": result}


def extract_command(args: dict[str, Any], payload: dict[str, Any]) -> str:
    for key in ("command", "cmd", "shell_command"):
        val = args.get(key) or payload.get(key)
        if isinstance(val, str) and val.strip():
            return redact(val.strip())[:MAX_COMMAND]
    argv = args.get("argv") or payload.get("argv")
    if isinstance(argv, list) and argv:
        return redact(" ".join(str(x) for x in argv))[:MAX_COMMAND]
    return ""


def extract_exit_code(payload: dict[str, Any]) -> int | None:
    for key in ("exit_code", "exit", "returncode", "return_code"):
        val = payload.get(key)
        if isinstance(val, bool) or val is None:
            continue
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    return None


def extract_output(payload: dict[str, Any]) -> str:
    for key in ("output", "stdout", "stderr", "result", "error"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def preview_of(output: str) -> str:
    text = redact((output or "").strip())
    if not text:
        return ""
    # Prefer last non-empty line for failures/noise
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    pick = lines[-1] if lines else text
    pick = " ".join(pick.split())
    if len(pick) > MAX_PREVIEW:
        pick = pick[: MAX_PREVIEW - 1] + "…"
    return pick


def extract_workdir(args: dict[str, Any], payload: dict[str, Any]) -> str:
    for key in ("workdir", "cwd", "working_directory"):
        val = args.get(key) or payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().replace("\\", "/")[:MAX_WORKDIR]
    return ""


def status_of(exit_code: int | None) -> str:
    if exit_code is None:
        return "unknown"
    if exit_code == 0:
        return "ok"
    return "fail"


def record_command(
    *,
    tool: str,
    command: str,
    exit_code: int | None,
    workdir: str,
    preview: str,
    max_items: int = MAX_ITEMS,
) -> list[dict[str, Any]]:
    state = load_state()
    items: list[dict[str, Any]] = [
        it for it in state.get("items", []) if isinstance(it, dict) and it.get("command")
    ]
    key = command
    index = {it["command"]: i for i, it in enumerate(items)}
    ts = now_iso()
    entry = {
        "command": command,
        "exit_code": exit_code,
        "status": status_of(exit_code),
        "workdir": workdir,
        "preview": preview,
        "tool": tool,
        "ts": ts,
        "runs": 1,
    }
    if key in index:
        prev = items[index[key]]
        entry["runs"] = int(prev.get("runs") or 1) + 1
        items[index[key]] = entry
    else:
        items.append(entry)
    if len(items) > max_items:
        items = items[-max_items:]
    state["items"] = items
    save_state(state)
    return items


def list_commands() -> list[dict[str, Any]]:
    state = load_state()
    items = state.get("items")
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict) and it.get("command")]


def clear_commands() -> None:
    save_state({"items": []})


def to_markdown(items: list[dict[str, Any]] | None = None) -> str:
    rows = items if items is not None else list_commands()
    if not rows:
        return "(command-tray is empty)"
    lines = []
    for i, it in enumerate(rows, 1):
        status = it.get("status") or "?"
        code = it.get("exit_code")
        code_s = "" if code is None else str(code)
        cmd = it["command"]
        if code_s:
            lines.append(f"{i}. `{cmd}` — {status} ({code_s})")
        else:
            lines.append(f"{i}. `{cmd}` — {status}")
    return "\n".join(lines)
