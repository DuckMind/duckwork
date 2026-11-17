# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Load the plugin through Duckwork's real plugin loader.

Skipped unless ``duckwork_cli`` is importable (it is in the nightly
``upstream-duckwork`` workflow, which installs Fordex/duckwork-agent
``main``). Each scenario runs in a fresh subprocess with its own temporary
``DUCKWORK_HOME`` so Duckwork's process-global plugin state cannot bleed between
cases.

Two install routes, chosen by what is present in the environment:

- ``entrypoint``: ``duckwork-tenuo`` is pip-installed, Duckwork finds the
  ``duckwork_agent.plugins`` entry point.
- ``directory``: the repo tree is copied to ``$DUCKWORK_HOME/plugins/duckwork-tenuo``
  the way ``duckwork plugins install tenuo-ai/duckwork-tenuo`` clones it; the
  package must NOT be pip-installed, so only the clone can satisfy it.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("duckwork_cli.plugins")

ROOT = Path(__file__).resolve().parents[1]
_IGNORE = shutil.ignore_patterns(
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "*.egg-info",
    "__pycache__",
    ".pytest_cache",
    "duckwork-agent",  # workflow checks Duckwork out here; do not copy it into the fake plugin
)


def _plugin_installed() -> bool:
    try:
        importlib.metadata.distribution("duckwork-tenuo")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


_DRIVER = textwrap.dedent(
    """
    import base64, json, os, sys
    home = os.environ["DUCKWORK_HOME"]
    configured = os.environ["HT_CONFIGURED"] == "1"
    if configured:
        from tenuo import SigningKey, Subpath, Warrant, Wildcard
        root, agent = SigningKey.generate(), SigningKey.generate()
        w = (Warrant.mint_builder().holder(agent.public_key)
             .capability("read_file", path=Subpath("/data"))
             .capability("web_search", query=Wildcard()).ttl(600).mint(root))
        os.environ["TENUO_SIGNING_KEY"] = base64.b64encode(agent.secret_key_bytes()).decode()
        entry = (f"      warrant: {base64.b64encode(w.to_bytes()).decode()}\\n"
                 f"      trusted_root: {base64.b64encode(root.public_key.to_bytes()).decode()}\\n"
                 f"      signing_key_env: TENUO_SIGNING_KEY\\n")
    else:
        entry = ""
    with open(os.path.join(home, "config.yaml"), "w") as fh:
        fh.write("plugins:\\n  enabled:\\n    - duckwork-tenuo\\n  entries:\\n    duckwork-tenuo:\\n" + entry)
    assert "duckwork_tenuo" not in sys.modules
    from duckwork_cli.plugins import PluginManager, invoke_hook
    pm = PluginManager()
    pm.discover_and_load()
    plugin = next((p for p in pm.list_plugins() if p["name"] == "duckwork-tenuo"), None)
    out = {
        "plugin": plugin,
        "skill": pm.find_plugin_skill("duckwork-tenuo:tenuo-scope") is not None,
        "deny": invoke_hook("pre_tool_call", tool_name="terminal", args={"command": "ls"}, session_id="s1"),
        "allow": invoke_hook("pre_tool_call", tool_name="read_file", args={"path": "/data/x"}, session_id="s1"),
        "audit_exists": os.path.exists(os.path.join(home, "tenuo", "audit.jsonl")),
        "loaded_from": sys.modules["duckwork_tenuo"].__file__,
    }
    print("RESULT " + json.dumps(out))
    """
)


def _run(mode: str, configured: bool, tmp_path: Path) -> dict:
    home = tmp_path / f"home-{mode}-{int(configured)}"
    (home / "plugins").mkdir(parents=True)
    if mode == "directory":
        shutil.copytree(ROOT, home / "plugins" / "duckwork-tenuo", ignore=_IGNORE)
    env = {k: v for k, v in os.environ.items() if not k.startswith("TENUO_")}
    env.update({"DUCKWORK_HOME": str(home), "HT_CONFIGURED": "1" if configured else "0"})
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER], cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    line = next(row for row in proc.stdout.splitlines() if row.startswith("RESULT "))
    result = json.loads(line[len("RESULT "):])
    result["stderr"] = proc.stderr
    return result


@pytest.mark.skipif(_plugin_installed(), reason="directory route needs the package NOT pip-installed")
class TestDirectoryRoute:
    def test_configured_enforces(self, tmp_path):
        r = _run("directory", True, tmp_path)
        assert r["plugin"] and r["plugin"]["source"] == "user" and r["plugin"]["error"] is None, r["plugin"]
        assert r["plugin"]["hooks"] == 5 and r["skill"]
        assert r["deny"] and r["deny"][0]["action"] == "block"
        assert r["allow"] == []
        assert r["audit_exists"]
        assert "/plugins/duckwork-tenuo/duckwork_tenuo/" in r["loaded_from"]

    def test_unconfigured_is_a_loud_noop(self, tmp_path):
        r = _run("directory", False, tmp_path)
        assert r["plugin"]["hooks"] == 5 and r["plugin"]["error"] is None
        assert r["deny"] == [] and r["allow"] == []
        assert "NOT enforced" in r["stderr"]


@pytest.mark.skipif(not _plugin_installed(), reason="entrypoint route needs the package pip-installed")
class TestEntrypointRoute:
    def test_configured_enforces(self, tmp_path):
        r = _run("entrypoint", True, tmp_path)
        assert r["plugin"] and r["plugin"]["source"] == "entrypoint" and r["plugin"]["error"] is None, r["plugin"]
        assert r["plugin"]["hooks"] == 5 and r["skill"]
        assert r["deny"] and r["deny"][0]["action"] == "block"
        assert r["allow"] == []
        assert r["audit_exists"]

    def test_unconfigured_is_a_loud_noop(self, tmp_path):
        r = _run("entrypoint", False, tmp_path)
        assert r["plugin"]["hooks"] == 5 and r["deny"] == [] and r["allow"] == []
        assert "NOT enforced" in r["stderr"]
