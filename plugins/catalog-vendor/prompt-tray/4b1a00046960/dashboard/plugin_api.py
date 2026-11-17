"""Dashboard/Desktop backend — mounted at /api/plugins/prompt-tray/."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Request

_ROOT = Path(__file__).resolve().parent.parent
_root_str = str(_ROOT)
if _root_str in sys.path:
    sys.path.remove(_root_str)
sys.path.insert(0, _root_str)

import prompt_store  # noqa: E402

router = APIRouter()


def _payload(request_json: object) -> dict:
    if isinstance(request_json, dict):
        return request_json
    return {}


@router.get("/prompts")
async def prompts() -> dict:
    items = prompt_store.list_prompts()
    return {"ok": True, "count": len(items), "items": items}


@router.post("/add")
async def add(request: Request) -> dict:
    try:
        body = _payload(await request.json())
    except Exception:
        body = {}
    return prompt_store.add_prompt(str(body.get("title") or ""), str(body.get("body") or ""))


@router.post("/delete")
async def delete(request: Request) -> dict:
    try:
        body = _payload(await request.json())
    except Exception:
        body = {}
    return prompt_store.delete_prompt(str(body.get("id") or ""))
