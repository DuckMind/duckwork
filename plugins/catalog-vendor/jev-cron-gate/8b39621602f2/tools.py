"""Handlers for the jev_cron_gate tool."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import gate

NAME_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
WRAPPER = '''#!/usr/bin/env python3
# jev-cron-gate wrapper (generated). Gate config: <DUCKWORK_HOME>/jev-cron-gates/{name}.json
import sys
sys.path.insert(0, {plugin_dir!r})
import gate
gate.main([{name!r}])
'''


def _scripts_dir() -> Path:
    return Path(gate.duckwork_home()) / "scripts"


def _wrapper_path(name: str) -> Path:
    return _scripts_dir() / f"jev_gate_{name}.py"


def _config_path(name: str) -> Path:
    return Path(gate.gates_dir()) / f"{name}.json"


def _ok(**kw) -> str:
    return json.dumps({"ok": True, **kw})


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


def setup(a: dict) -> str:
    name, question = a.get("name", ""), (a.get("question") or "").strip()
    if not NAME_RE.match(name):
        return _err("name must match [a-z0-9_-]{1,40}")
    if not question:
        return _err("question is required")
    try:
        sources = json.loads(a.get("sources") or "[]")
        assert isinstance(sources, list)
    except Exception:
        return _err("sources must be a JSON array")
    cfg = {"question": question, "sources": sources,
           "skip_below": float(a.get("skip_below", 0.2)),
           "max_consecutive_skips": int(a.get("max_consecutive_skips", 4))}
    os.makedirs(gate.gates_dir(), exist_ok=True)
    _config_path(name).write_text(json.dumps(cfg, indent=2))
    _scripts_dir().mkdir(parents=True, exist_ok=True)
    w = _wrapper_path(name)
    w.write_text(WRAPPER.format(name=name, plugin_dir=str(Path(__file__).parent)))
    w.chmod(0o755)
    job = a.get("job_id") or "<job_id>"
    return _ok(config=str(_config_path(name)), script=w.name,
               attach=f"duckwork cron edit {job} --script {w.name}",
               note="Run `test` first, then attach. Attaching replaces any existing pre-run script on the job.")


def test(a: dict) -> str:
    name = a.get("name", "")
    try:
        cfg = json.loads(_config_path(name).read_text())
    except (OSError, ValueError):
        return _err(f"no gate config for '{name}'")
    state = gate.build_state(cfg, 0)
    score, err = gate.ask_jev(state, cfg["question"])
    wake = True if score is None else score >= float(cfg.get("skip_below", 0.2))
    return _ok(score=score, error=err, would_wake=wake, state_chars=len(state), state_preview=state[:600])


def status(a: dict) -> str:
    log = Path(gate.gates_dir()) / "log.jsonl"
    stats: dict = {}
    try:
        for line in log.read_text().splitlines():
            r = json.loads(line)
            if a.get("name") and r.get("gate") != a["name"]:
                continue
            s = stats.setdefault(r["gate"], {"runs": 0, "skipped": 0, "errors": 0, "last": None})
            s["runs"] += 1
            s["skipped"] += 0 if r["wake"] else 1
            s["errors"] += 1 if r.get("score") is None else 0
            s["last"] = r
    except OSError:
        pass
    for s in stats.values():
        s["skip_rate"] = round(s["skipped"] / s["runs"], 2) if s["runs"] else 0
    return _ok(gates=stats, log=str(log))


def remove(a: dict) -> str:
    name = a.get("name", "")
    if not NAME_RE.match(name):
        return _err("bad name")
    removed = []
    for p in (_config_path(name), _wrapper_path(name), Path(gate.gates_dir()) / f"{name}.state.json"):
        if p.exists():
            p.unlink()
            removed.append(str(p))
    return _ok(removed=removed, note="Also detach it: duckwork cron edit <job_id> --script ''")


def handle(args, **_kw) -> str:
    a = args or {}
    fn = {"setup": setup, "test": test, "status": status, "remove": remove}.get(a.get("action"))
    if not fn:
        return _err("action must be setup|test|status|remove")
    try:
        return fn(a)
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")
