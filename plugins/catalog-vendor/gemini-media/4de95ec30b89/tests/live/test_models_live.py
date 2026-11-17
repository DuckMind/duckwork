# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
# Copyright 2026 bytecakelake
# SPDX-License-Identifier: Apache-2.0
"""Calls the real Gemini API. Run with:  pytest -m live  (needs GEMINI_API_KEY in the environment)."""

import os

import pytest

from duckwork_gemini_media import models
from duckwork_gemini_media.auth import ApiKeyAuth

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set"),
]


def test_models_list_live_contains_defaults():
    catalog, source = models.get_catalog(ApiKeyAuth(), force_refresh=True)
    assert source == "live"
    image_ids = [m.id for m in models.models_of(models.IMAGE, catalog)]
    video_ids = [m.id for m in models.models_of(models.VIDEO, catalog)]
    assert image_ids and video_ids
    assert models.default_id(models.IMAGE, catalog) in image_ids
    assert models.default_id(models.VIDEO, catalog) in video_ids
    print("image:", image_ids)
    print("video:", video_ids)
