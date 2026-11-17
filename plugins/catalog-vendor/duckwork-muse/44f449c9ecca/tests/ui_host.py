"""Owned ephemeral native Dashboard for browser acceptance; Ctrl-C cleans its home."""

import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile

os.environ["DUCKWORK_DISABLE_LAZY_INSTALLS"] = "1"
os.environ["DUCKWORK_DATA_DIR_SUFFIX"] = "-muse-isolated-test"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, os.environ["DUCKWORK_SOURCE"])
with tempfile.TemporaryDirectory(prefix="muse-browser-") as directory:
    home = Path(directory)
    os.environ["DUCKWORK_HOME"] = str(home)
    os.environ["DUCKWORK_DASHBOARD_SESSION_TOKEN"] = "muse-isolated-browser-fixture"
    from duckwork_muse.store import Store
    from duckwork_muse.host import DuckworkHost, profile_scope
    from duckwork_muse.service import Companion

    for target, title in ((home, "Orchid"), (home / "profiles/cedar", "Cedar")):
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.yaml").write_text(
            "plugins:\n  enabled: [duckwork-muse]\n  isolation: in-process\ntimezone: UTC\n"
        )
        shutil.copytree(
            root,
            target / "plugins/duckwork-muse",
            ignore=shutil.ignore_patterns(".git", ".serena", "__pycache__"),
        )
        with profile_scope(target):
            store = Store(target)
            host = DuckworkHost(store, plugin_root=target / "plugins/duckwork-muse")
            host.initialize()
            service = Companion(store, host)
            service.signal(
                "fixture-signal", "fixture-chat", "Research my synthetic project"
            )
            service.goal_create(
                {
                    "id": "research",
                    "title": title + " research",
                    "description": "Compare the fixture alternatives.",
                    "completion_criteria": "Verified findings and original sources",
                    "signal_id": "fixture-signal",
                }
            )
            service.idea_add(
                {
                    "title": title + " next idea",
                    "rationale": "Follow the verified synthetic source",
                    "goal_id": "research",
                }
            )
            for n in range(107):
                service.feed_add(
                    {
                        "event_key": "fixture-" + str(n),
                        "title": title + " article " + str(n),
                        "content": "# Finding\n\nThis is synthetic evidence for browser testing.\n\n"
                        + "Useful detail. " * 100,
                        "sources": ["fixture:public-source"],
                        "why": "A useful next step for the fixture goal.",
                        "goal_id": "research",
                    }
                )
    from duckwork_cli.web_server import app
    import uvicorn

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    app.state.bound_host = "127.0.0.1"
    record = {
        "url": f"http://127.0.0.1:{port}/muse",
        "home": str(home),
        "pid": os.getpid(),
    }
    Path(os.environ["MUSE_EVIDENCE_DIR"], "logs/ui-server.json").write_text(
        json.dumps(record)
    )
    print(json.dumps(record), flush=True)
    # No gateway, model, scheduler, lifespan workers, or external messages.
    uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off")).run(
        sockets=[sock]
    )
