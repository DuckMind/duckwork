"""Dashboard/Desktop backend — mounted at /api/plugins/sketch-pad/."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Request

_ROOT = Path(__file__).resolve().parent.parent
_root_str = str(_ROOT)
if _root_str in sys.path:
    sys.path.remove(_root_str)
sys.path.insert(0, _root_str)

import sketch_store  # noqa: E402

router = APIRouter()


@router.get("/last")
async def last() -> dict:
    return sketch_store.last_sketch()


@router.post("/save")
async def save(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    blob = sketch_store.decode_png_base64(str(payload.get("png_base64") or ""))
    if blob is None:
        return {"ok": False, "error": "Invalid or oversized PNG."}
    try:
        return sketch_store.save_png(blob)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
