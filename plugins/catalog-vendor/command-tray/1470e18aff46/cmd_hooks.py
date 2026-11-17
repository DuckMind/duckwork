"""post_tool_call observer — collect terminal commands into the tray."""

from __future__ import annotations

import cmd_store

WATCH_TOOLS = cmd_store.WATCH_TOOLS


def on_post_tool_call(tool_name: str, args: dict, result: str, **kwargs) -> None:
    del kwargs
    try:
        if tool_name not in WATCH_TOOLS:
            return
        arg_map = args if isinstance(args, dict) else {}
        payload = cmd_store.parse_tool_payload(result)
        command = cmd_store.extract_command(arg_map, payload)
        if not command:
            return
        # Skip silent background notify-only envelopes without a real command run
        if arg_map.get("background") is True and payload.get("exit_code") is None:
            # Still record if we have a command — background start is useful
            pass
        exit_code = cmd_store.extract_exit_code(payload)
        workdir = cmd_store.extract_workdir(arg_map, payload)
        preview = cmd_store.preview_of(cmd_store.extract_output(payload))
        cmd_store.record_command(
            tool=tool_name,
            command=command,
            exit_code=exit_code,
            workdir=workdir,
            preview=preview,
        )
    except Exception:
        return
