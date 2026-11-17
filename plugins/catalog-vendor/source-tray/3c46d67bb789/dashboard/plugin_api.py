"""Dashboard/Desktop backend — mounted at /api/plugins/source-tray/."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

_ROOT = Path(__file__).resolve().parent.parent
_root_str = str(_ROOT)
if _root_str in sys.path:
    sys.path.remove(_root_str)
sys.path.insert(0, _root_str)

import tray_store  # noqa: E402

router = APIRouter()


@router.get("/tray")
async def tray() -> dict:
    items = tray_store.list_sources()
    return {"ok": True, "count": len(items), "items": items}


@router.post("/clear")
async def clear() -> dict:
    tray_store.clear_sources()
    return {"ok": True, "count": 0, "items": []}
