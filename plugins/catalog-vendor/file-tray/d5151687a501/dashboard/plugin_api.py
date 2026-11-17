"""Dashboard/Desktop backend — mounted at /api/plugins/file-tray/."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

_ROOT = Path(__file__).resolve().parent.parent
_root_str = str(_ROOT)
if _root_str in sys.path:
    sys.path.remove(_root_str)
sys.path.insert(0, _root_str)

import file_store  # noqa: E402

router = APIRouter()


@router.get("/tray")
async def tray() -> dict:
    items = file_store.list_files()
    return {"ok": True, "count": len(items), "items": items}


@router.post("/clear")
async def clear() -> dict:
    file_store.clear_files()
    return {"ok": True, "count": 0, "items": []}
