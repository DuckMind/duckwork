"""devkit: per-session scratchpad for Duckwork (the dev pane builds on it)."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from .scratchpad import guidance, store, tool

logger = logging.getLogger(__name__)

RECONCILE_INTERVAL_S = 3600
# How often the thread checks the shared hourly stamp: a restart delays cleanup by at most this.
RECONCILE_POLL_S = 600
_reconciler_started = False
_idle_days = store.IDLE_DAYS


def _state_db() -> Path:
    from duckwork_constants import get_duckwork_home
    return Path(get_duckwork_home()) / "state.db"


def _reconcile_once() -> None:
    root = store.default_root()
    stamp = root / ".last_reconcile"
    try:
        if stamp.exists() and time.time() - stamp.stat().st_mtime < RECONCILE_INTERVAL_S:
            return
        root.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        removed = store.reconcile(root, _state_db(), idle_days=_idle_days)
        for row in removed:
            logger.info("devkit scratchpad: removed buffers of session %s (%s)", row["session_id"], row["reason"])
    except Exception:  # cleanup is best-effort; never take a Duckwork process down
        logger.warning("devkit scratchpad reconcile failed", exc_info=True)


def _reconcile_loop() -> None:
    while True:
        _reconcile_once()
        time.sleep(RECONCILE_POLL_S)


def _on_turn(**kw):
    session_id = kw.get("session_id")
    if session_id:
        try:
            store.touch(store.default_root(), str(session_id))
        except Exception:
            logger.debug("devkit scratchpad: stamp update failed", exc_info=True)
    return guidance.reminder(store.default_root, **kw)


def register(ctx):
    global _reconciler_started, _idle_days
    try:
        _idle_days = float(ctx.get_config("idle_days", default=store.IDLE_DAYS))
    except Exception:
        _idle_days = store.IDLE_DAYS
    tool.bind(ctx)
    ctx.register_tool(name="scratchpad", toolset="devkit", schema=tool.SCHEMA, handler=tool.handle)
    ctx.register_hook("pre_llm_call", _on_turn)
    if not _reconciler_started:
        _reconciler_started = True
        threading.Thread(target=_reconcile_loop, name="devkit-scratchpad-reconcile", daemon=True).start()
