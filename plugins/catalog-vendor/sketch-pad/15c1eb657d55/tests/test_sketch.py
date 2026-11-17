"""Local checks that do not require Duckwork."""

from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DUCKWORK_HOME"] = tempfile.mkdtemp(prefix="sketch-pad-test-")

import sketch_store
import sketch_tools


def _tiny_png() -> bytes:
    # 1x1 PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ZkAAAAASUVORK5CYII="
    )


def test_reject_garbage() -> None:
    assert sketch_store.decode_png_base64("not-png") is None
    assert sketch_store.decode_png_base64("") is None
    assert sketch_store.decode_png_base64("AAAA") is None


def test_save_roundtrip() -> None:
    blob = _tiny_png()
    b64 = base64.b64encode(blob).decode("ascii")
    decoded = sketch_store.decode_png_base64("data:image/png;base64," + b64)
    assert decoded == blob
    meta = sketch_store.save_png(decoded)
    assert meta["ok"] is True
    vision = Path(meta["path"])
    assert vision.is_file()
    assert vision.parent.name == "images"
    assert vision.name.startswith("sketch_pad_")
    last = sketch_store.last_sketch()
    assert last["path"] == meta["path"]
    import json

    tool = json.loads(sketch_tools.sketch_pad_last({}))
    assert tool["ok"] is True
    assert tool["path"] == meta["path"]
    assert (Path(os.environ["DUCKWORK_HOME"]) / "images" / "sketch_pad_last.png").is_file()


if __name__ == "__main__":
    test_reject_garbage()
    test_save_roundtrip()
    print("ok")
