"""Where is a Duckwork checkout? The plugin needs `duckwork_constants` to resolve <home>, and a clone in
Documents/ is no longer beside one — so this is the one place that knows how to find it."""
import os
import pathlib
import sys


def CANDIDATES():
    local = os.environ.get("LOCALAPPDATA") or str(pathlib.Path.home() / ".local" / "share")
    return [
        pathlib.Path(local) / "duckwork" / "duckwork-agent",
        pathlib.Path.home() / "duckwork-agent",
        pathlib.Path("/usr/local/src/duckwork-agent"),
    ]


def agent_dir():
    env = os.environ.get("DUCKWORK_AGENT_DIR")
    if env:
        return pathlib.Path(env)
    for c in CANDIDATES():
        if (c / "duckwork_constants.py").is_file():
            return c
    raise RuntimeError(
        "no Duckwork checkout found; set DUCKWORK_AGENT_DIR=/path/to/duckwork-agent "
        "(git clone https://github.com/DuckMind/duckwork)")


def bootstrap_sys_path():
    d = agent_dir()
    if str(d) not in sys.path:
        # The checkout belongs to somebody else: never leave compiled artifacts of this run in it.
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(d))
    return d
