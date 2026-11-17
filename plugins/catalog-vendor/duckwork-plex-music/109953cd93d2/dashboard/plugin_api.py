"""Plex Music backend — self-update checker/installer only.

Mounted at /api/plugins/plex-music/. All playback is direct Plex HTTP
from the desktop pane; this backend just compares the local plugin.yaml
version against GitHub and installs updates from the repo tarball.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}
