"""Dashboard/Desktop backend — mounted at /api/plugins/done-bell/."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Request

_ROOT = Path(__file__).resolve().parent.parent
_root_str = str(_ROOT)
if _root_str in sys.path:
    sys.path.remove(_root_str)
sys.path.insert(0, _root_str)

import bell_store  # noqa: E402

router = APIRouter()


def _payload(request_json: object) -> dict:
    if isinstance(request_json, dict):
        return request_json
    return {}


@router.get("/status")
async def status() -> dict:
    return bell_store.snapshot()


@router.post("/settings")
async def settings(request: Request) -> dict:
    try:
        body = _payload(await request.json())
    except Exception:
        body = {}
    settings = bell_store.patch_settings(body)
    snap = bell_store.snapshot()
    snap["settings"] = settings
    return snap


@router.post("/test")
async def test_ring() -> dict:
    event = bell_store.record_event(
        "done",
        platform="desktop",
        detail="test",
        needs_you=False,
    )
    return {"ok": True, "event": event, "settings": bell_store.get_settings()}
