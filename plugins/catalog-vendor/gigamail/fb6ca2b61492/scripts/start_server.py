# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Start the user's GigaMail installation with a consistent data directory.

Only the Python standard library is required. No downloads, shell execution,
mailbox login, approval, or Duckwork configuration writes happen here.
"""
import ctypes
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SETTINGS = {"server_command", "data_root", "mail_data_dir"}


def load_settings(env):
    data_dir = env.get("PLUGIN_DATA")
    if not data_dir:
        return {}
    config = Path(data_dir) / "config.json"
    if not config.exists():
        return {}
    settings = json.loads(config.read_text(encoding="utf-8-sig"))
    if not isinstance(settings, dict) or set(settings) - SETTINGS:
        raise ValueError("config.json must contain only server_command, data_root and mail_data_dir")
    for key, value in settings.items():
        if not isinstance(value, str) or not value.strip() or "\0" in value:
            raise ValueError(f"config.json {key} must be a non-empty string")
    return settings


def absolute_directory(value, label):
    directory = Path(value).expanduser()
    if not directory.is_absolute():
        raise ValueError(f"{label} must be an absolute directory path")
    return str(directory)


def windows_appdata(env):
    if env.get("APPDATA"):
        return absolute_directory(env["APPDATA"], "APPDATA")
    # Duckwork filters environment variables. Query Windows itself so roaming
    # profile redirection also works; do not guess from a user name.
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 26, None, 0, buffer)
    if result != 0 or not buffer.value:
        raise ValueError("Cannot locate Windows AppData; set data_root in the plugin config.json")
    return buffer.value


def prepare_launch(env=None, *, platform=None, home=None):
    child_env = dict(os.environ if env is None else env)
    settings = load_settings(child_env)
    platform = platform or sys.platform
    command = settings.get("server_command") or child_env.get("GIGAMAIL_SERVER") or "gigamail-server"
    if "\0" in command or "\n" in command or "\r" in command:
        raise ValueError("server_command must be one executable, without arguments")
    if ("/" in command or "\\" in command) and not Path(command).is_absolute():
        raise ValueError("server_command must be an executable name or an absolute path")
    executable = shutil.which(command, path=child_env.get("PATH"))
    if not executable:
        raise ValueError("gigamail-server was not found. Install GigaMail or set server_command in the plugin config.json")

    explicit_root = (settings.get("data_root") or child_env.get("GIGAMAIL_ROOT")
                     or child_env.get("ADE_ROOT"))
    if explicit_root:
        root = absolute_directory(explicit_root, "data_root")
    elif platform == "win32":
        appdata = windows_appdata(child_env)
        child_env["APPDATA"] = appdata
        root = str(Path(appdata) / "ADE")
    else:
        root = str(Path(home) / ".ade" if home is not None else Path.home() / ".ade")
    child_env["GIGAMAIL_ROOT"] = root
    # Keep the legacy alias coherent for older installations.
    child_env["ADE_ROOT"] = root
    if "data_root" in settings:
        child_env.pop("GIGAMAIL_DATA_DIR", None)
        child_env.pop("ADE_MAIL_DATA_DIR", None)
    if "mail_data_dir" in settings:
        mail_root = absolute_directory(settings["mail_data_dir"], "mail_data_dir")
        child_env["GIGAMAIL_DATA_DIR"] = mail_root
        child_env["ADE_MAIL_DATA_DIR"] = mail_root
    return executable, [executable], child_env


def run_server(executable, argv, env):
    if sys.platform == "win32":
        # Windows execve starts another process rather than replacing this
        # one. Wait for the server so the MCP client owns its full lifetime.
        return subprocess.call(argv, env=env)
    os.execve(executable, argv, env)
    return 0


def main():
    try:
        executable, argv, env = prepare_launch()
        # Preserve stdin/stdout for MCP and the server's exit/signal behavior.
        return run_server(executable, argv, env)
    except (OSError, ValueError, AttributeError) as error:
        print(f"GigaMail plugin: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
