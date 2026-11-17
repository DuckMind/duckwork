"""Handflow backend routes — what the desktop pane reads and clicks.

Mounted by the Duckwork server at ``/api/plugins/handflow/`` and reached from the
pane as ``ctx.rest('/active')``::

    GET  /health                          liveness + resolved state dir
    GET  /active                          the active plan (null when there is none)
    GET  /plans?limit=20                  recent plans, newest first
    GET  /plans/{plan_id}                 one plan
    POST /plans/{plan_id}/steps/{step_id} {"op": "complete|begin|block|reopen", "note": "…"}
    POST /active                          {"plan_id": "…"} pin a plan

Reads and writes the same JSON files the ``handflow`` agent tool uses, so the
pane and the agent can never disagree. Nothing here calls a model, opens a
socket, or shells out.

Import note: the loader imports this file by path with the plugin root *not* on
``sys.path``, so the store is reached by inserting the package root here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

_PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

try:  # normal case: plugin root now on sys.path, inner package importable
    from handflow import store  # type: ignore
except ImportError:  # pragma: no cover - defence if the root is already a package
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from handflow import store  # type: ignore

router = APIRouter(tags=["handflow"])

_OP_STATUS = {
    "begin": store.IN_PROGRESS,
    "start": store.IN_PROGRESS,
    "complete": store.COMPLETED,
    "done": store.COMPLETED,
    "block": store.BLOCKED,
    "reopen": store.NOT_STARTED,
    "reset": store.NOT_STARTED,
}


def _view(plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """One plan as the pane wants it — rendered text included, so the pane and
    the agent read the exact same lines."""
    if not plan:
        return {"ok": True, "plan": None, "text": "", "counts": None, "state_dir": str(store.state_root())}
    store.reindex(plan)
    counts = store.counts(plan)
    current = store.find_step(plan, None)
    return {
        "ok": True,
        "plan": plan,
        "text": store.render(plan),
        "counts": counts,
        "progress": (counts["done"] / counts["total"]) if counts.get("total") else 0.0,
        "current_step_id": (current or {}).get("id"),
        "state_dir": str(store.state_root()),
    }


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "state_dir": str(store.state_root()), "plans_dir": str(store.plans_dir())}


@router.get("/active")
def active() -> JSONResponse:
    return JSONResponse(_view(store.active_plan()))


@router.get("/plans")
def plans(limit: int = 20) -> Dict[str, Any]:
    return {
        "ok": True,
        "active_plan_id": store.active_plan_id(),
        "plans": [
            {
                "plan_id": p.get("id"),
                "goal": p.get("goal"),
                "status": p.get("status"),
                "counts": store.counts(p),
                "updated_at": p.get("updated_at"),
            }
            for p in store.list_plans(limit=limit)
        ],
    }


@router.get("/plans/{plan_id}")
def one_plan(plan_id: str) -> JSONResponse:
    plan = store.load(plan_id)
    if plan is None:
        return JSONResponse({"ok": False, "error": f"no plan {plan_id}"}, status_code=404)
    return JSONResponse(_view(plan))


@router.post("/plans/{plan_id}/steps/{step_id}")
def mark_step(plan_id: str, step_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    body = payload or {}
    op = str(body.get("op") or "").strip().lower()
    if op not in _OP_STATUS:
        return JSONResponse({"ok": False, "error": f"op must be one of {', '.join(sorted(_OP_STATUS))}"}, status_code=400)
    plan = store.load(plan_id)
    if plan is None:
        return JSONResponse({"ok": False, "error": f"no plan {plan_id}"}, status_code=404)
    store.reindex(plan)
    try:
        store.mark_step(plan, step_id, _OP_STATUS[op], str(body.get("note") or ""))
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    status = _OP_STATUS[op]
    store.close_if_done(plan)
    if status == store.NOT_STARTED:
        store.reopen(plan)
    store.save(plan)
    return JSONResponse(_view(plan))


@router.post("/active")
def set_active(payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    body = payload or {}
    plan_id = str(body.get("plan_id") or "").strip()
    plan = store.load(plan_id) if plan_id else None
    if plan is None:
        return JSONResponse({"ok": False, "error": f"no plan {plan_id!r}"}, status_code=404)
    store.set_active(plan_id)
    return JSONResponse(_view(plan))


# Directory the pane's own diagnostics can be told about via the environment.
def state_dir_hint() -> str:
    return os.environ.get("HANDFLOW_HOME", "") or str(store.state_root())
