"""Save the last confirmed sketch PNG where Duckwork vision can read it."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ID = "sketch-pad"
MAX_BYTES = 800_000
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def duckwork_home() -> Path:
    env = os.environ.get("DUCKWORK_HOME")
    if env:
        return Path(env)
    try:
        from duckwork_constants import get_duckwork_home  # type: ignore

        return Path(get_duckwork_home())
    except Exception:
        pass
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore

        folder = Path(plugin_data_dir(PLUGIN_ID))
        if folder.parent.name == "plugin-data":
            return folder.parent.parent
    except Exception:
        pass
    return Path.home() / ".duckwork"


def data_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore

        return plugin_data_dir(PLUGIN_ID)
    except Exception:
        path = duckwork_home() / "plugin-data" / PLUGIN_ID
        path.mkdir(parents=True, exist_ok=True)
        return path


def vision_images_dir() -> Path:
    """Desktop/clipboard uploads live here; vision_analyze host-reads this dir."""
    path = duckwork_home() / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def last_png_path() -> Path:
    return data_dir() / "last.png"


def meta_path() -> Path:
    return data_dir() / "last.json"


def _atomic_write(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decode_png_base64(raw: str) -> bytes | None:
    text = (raw or "").strip()
    if text.startswith("data:image/png;base64,"):
        text = text.split(",", 1)[1]
    if not text:
        return None
    try:
        blob = base64.b64decode(text, validate=True)
    except Exception:
        try:
            blob = base64.b64decode(text)
        except Exception:
            return None
    if len(blob) < 24 or len(blob) > MAX_BYTES:
        return None
    if not blob.startswith(PNG_MAGIC):
        return None
    return blob


def save_png(blob: bytes) -> dict[str, Any]:
    _atomic_write(last_png_path(), blob)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    vision_path = vision_images_dir() / f"sketch_pad_{stamp}.png"
    _atomic_write(vision_path, blob)
    _atomic_write(vision_images_dir() / "sketch_pad_last.png", blob)
    meta = {
        "ok": True,
        "path": str(vision_path),
        "bytes": len(blob),
        "ts": now_iso(),
    }
    meta_path().write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def last_sketch() -> dict[str, Any]:
    try:
        raw = json.loads(meta_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    candidates = [
        Path(str(raw["path"])) if raw.get("path") else None,
        vision_images_dir() / "sketch_pad_last.png",
        last_png_path(),
    ]
    path = next((p for p in candidates if p is not None and p.is_file()), None)
    if path is None:
        return {"ok": True, "path": None, "bytes": 0, "ts": None}
    return {
        "ok": True,
        "path": str(path),
        "bytes": path.stat().st_size,
        "ts": raw.get("ts"),
    }
