"""devkit backend for the Desktop scratchpad viewer: lists and removes only devkit's own folders."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter, HTTPException

_spec = importlib.util.spec_from_file_location(
    "devkit_scratchpad_store", Path(__file__).resolve().parent.parent / "scratchpad" / "store.py")
store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(store)

router = APIRouter()


def _run(fn, *args):
    try:
        return fn(*args)
    except store.ScratchpadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _state_db() -> Path:
    from duckwork_constants import get_duckwork_home
    return Path(get_duckwork_home()) / "state.db"


@router.get("/sessions")
async def sessions():
    rows = store.inventory(store.default_root())
    return {"sessions": store.with_existence(rows, store.db_session_ids(_state_db()))}


@router.delete("/sessions/{dir_name}")
async def remove_session(dir_name: str):
    return _run(store.remove_session_dir, store.default_root(), dir_name)


@router.get("/sessions/{dir_name}/buffers/{name}")
async def read_buffer(dir_name: str, name: str):
    return _run(store.read_in_dir, store.default_root(), dir_name, name)


@router.put("/sessions/{dir_name}/buffers/{name}")
async def save_buffer(dir_name: str, name: str, body: dict):
    content = body.get("content")
    try:
        return store.write_in_dir(store.default_root(), dir_name, name, content)
    except store.ScratchpadError as exc:
        status = 404 if "no buffer" in str(exc) or "no scratchpad" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.delete("/sessions/{dir_name}/buffers/{name}")
async def remove_buffer(dir_name: str, name: str):
    return _run(store.remove_buffer_in_dir, store.default_root(), dir_name, name)


@router.post("/clear")
async def clear(body: dict):
    root = store.default_root()
    if body.get("all") is True:
        return store.remove_all(root)
    dirs = body.get("dirs")
    if not isinstance(dirs, list) or not all(isinstance(d, str) for d in dirs):
        raise HTTPException(status_code=400, detail="body needs {\"all\": true} or {\"dirs\": [...]}")
    removed = []
    for dir_name in dirs:
        try:
            store.remove_session_dir(root, dir_name)
            removed.append(dir_name)
        except store.ScratchpadError:
            continue
    return {"removed": removed}
