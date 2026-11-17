"""MiniMax video generation backend.

Exposes MiniMax's Hailuo video models through the MiniMax video generation
API as a VideoGenProvider.

Supports three generation modes:
  - Text-to-video (T2V): prompt only
  - Image-to-video (I2V): image_url as first frame
  - Subject-reference-to-video (S2V): reference_image_urls as subject refs

All modes use the same async task API:
  1. POST {api}/v1/video_generation  -->  returns task_id
  2. GET  {api}/v1/query/video_generation?task_id=X  -->  poll until Success/Fail
  3. GET  {api}/v1/files/retrieve?file_id=X  -->  get download_url
  4. Download and cache locally.

Configuration (config.yaml):

    video_gen:
      provider: minimax
      minimax:
        api: https://api.minimax.io
        key_env: MINIMAX_PAYG_KEY
        model: MiniMax-Hailuo-2.3       # default for t2v/i2v
        model_s2v: S2V-01               # auto-used for subject reference
        # resolution: 768P              # optional, default depends on model
        # prompt_optimizer: true        # optional, defaults to true

All keys are optional. Defaults:
  - api:         https://api.minimax.io
  - key_env:     MINIMAX_API_KEY
  - model:       MiniMax-Hailuo-2.3
  - model_s2v:   S2V-01

Models:
  T2V: MiniMax-Hailuo-2.3, MiniMax-Hailuo-02, T2V-01-Director, T2V-01
  I2V: MiniMax-Hailuo-2.3, MiniMax-Hailuo-2.3-Fast, MiniMax-Hailuo-02,
       I2V-01-Director, I2V-01-live, I2V-01
  S2V: S2V-01

Camera control: Hailuo-2.3, Hailuo-02, and Director models support
[command] syntax in prompts (e.g. "[Push in], then [Pan left]").
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.video_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_RESOLUTION,
    VideoGenProvider,
    error_response,
    save_url_video,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

_MODELS = [
    {
        "id": "MiniMax-Hailuo-2.3",
        "display": "MiniMax Hailuo 2.3",
        "speed": "~2-3 min",
        "strengths": "Latest text-to-video and image-to-video with camera control. 768P/1080P, 6 or 10s.",
        "price": "PAYG / token plan",
        "modalities": ["text", "image"],
    },
    {
        "id": "MiniMax-Hailuo-2.3-Fast",
        "display": "MiniMax Hailuo 2.3 Fast",
        "speed": "~1 min",
        "strengths": "Faster image-to-video variant of Hailuo 2.3. 768P/1080P, 6 or 10s.",
        "price": "PAYG / token plan",
        "modalities": ["image"],
    },
    {
        "id": "MiniMax-Hailuo-02",
        "display": "MiniMax Hailuo 02",
        "speed": "~2-3 min",
        "strengths": "Previous-gen text-to-video and image-to-video. 512P/768P/1080P, 6 or 10s.",
        "price": "PAYG / token plan",
        "modalities": ["text", "image"],
    },
    {
        "id": "S2V-01",
        "display": "S2V-01 (Subject Reference)",
        "speed": "~2-3 min",
        "strengths": "Subject-reference-to-video: animate a character from reference images.",
        "price": "PAYG / token plan",
        "modalities": ["image"],
    },
]

# ---------------------------------------------------------------------------
# Polling config
# ---------------------------------------------------------------------------

_POLL_INTERVAL_S = 5.0
_POLL_DEADLINE_S = 600.0  # 10 minutes max

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_API = "https://api.minimax.io"
_DEFAULT_KEY_ENV = "MINIMAX_API_KEY"
_DEFAULT_MODEL = "MiniMax-Hailuo-2.3"
_DEFAULT_MODEL_S2V = "S2V-01"

# Max file size for base64 inline encoding (10 MB -- MiniMax allows 20MB
# but we keep 10MB to stay consistent with our other plugins).
_MAX_INLINE_BYTES = 10 * 1024 * 1024

# ---------------------------------------------------------------------------
# Input normalization (same pattern as dashscope/minimax image plugins)
# ---------------------------------------------------------------------------


def _to_data_uri(path: str) -> str:
    """Convert a local image file to a base64 data URI for the API.

    MiniMax accepts data URIs in first_frame_image and subject_reference
    image fields.  Local paths are detected and converted automatically so
    callers can pass file paths directly.

    Raises ``ValueError`` for missing files or unsupported sizes.
    """
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"Image file not found: {path}")
    if p.stat().st_size > _MAX_INLINE_BYTES:
        raise ValueError(
            f"Image too large for inline encoding ({p.stat().st_size} bytes, "
            f"max {_MAX_INLINE_BYTES}). Use a URL instead."
        )
    mime, _ = mimetypes.guess_type(str(p))
    if not mime or not mime.startswith("image/"):
        mime = "image/png"  # safe fallback
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _normalize_source(src: str) -> str:
    """Return a URL or data URI suitable for the MiniMax API.

    - http/https URLs and data URIs pass through unchanged.
    - Local file paths are converted to base64 data URIs.
    """
    if src.startswith(("http://", "https://", "data:")):
        return src
    return _to_data_uri(src)


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


def _load_config() -> Dict[str, Any]:
    """Read ``video_gen.minimax`` from config.yaml."""
    try:
        from duckwork_cli.config import load_config

        cfg = load_config()
        section = cfg.get("video_gen") if isinstance(cfg, dict) else None
        mm = section.get("minimax") if isinstance(section, dict) else None
        return mm if isinstance(mm, dict) else {}
    except Exception as exc:
        logger.debug("Could not load video_gen.minimax config: %s", exc)
        return {}


def _resolve_api(cfg: Dict[str, Any]) -> str:
    """Resolve the API base URL: config > default."""
    api = cfg.get("api", "")
    if isinstance(api, str) and api.strip():
        return api.strip().rstrip("/")
    return _DEFAULT_API


def _resolve_key_env(cfg: Dict[str, Any]) -> str:
    """Resolve the env var name holding the API key: config > default."""
    key_env = cfg.get("key_env", "")
    if isinstance(key_env, str) and key_env.strip():
        return key_env.strip()
    return _DEFAULT_KEY_ENV


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class MiniMaxVideoGenProvider(VideoGenProvider):
    """MiniMax video generation backend.

    Uses the MiniMax video generation API for text-to-video (T2V),
    image-to-video (I2V), and subject-reference-to-video (S2V).
    All modes are asynchronous: submit, poll, retrieve file, download.
    """

    @property
    def name(self) -> str:
        return "minimax"

    @property
    def display_name(self) -> str:
        return "MiniMax (Hailuo)"

    def is_available(self) -> bool:
        cfg = _load_config()
        key_env = _resolve_key_env(cfg)
        return bool(os.environ.get(key_env, "").strip())

    def list_models(self) -> List[Dict[str, Any]]:
        return list(_MODELS)

    def default_model(self) -> Optional[str]:
        return _DEFAULT_MODEL

    def capabilities(self) -> Dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
            "resolutions": ["768p", "1080p", "512p", "720p"],
            "max_duration": 10,
            "min_duration": 6,
            "supports_audio": False,
            "supports_negative_prompt": False,
            "max_reference_images": 1,
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "MiniMax (Hailuo)",
            "badge": "api-key",
            "tag": "Hailuo video models via MiniMax platform",
            "env_vars": [
                {
                    "key": "MINIMAX_PAYG_KEY",
                    "prompt": "MiniMax API key (PAYG)",
                    "url": "https://platform.minimax.io/user-center/basic-information/interface-key",
                },
            ],
        }

    # -----------------------------------------------------------------
    # Core generation
    # -----------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        duration: Optional[int] = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        resolution: str = DEFAULT_RESOLUTION,
        negative_prompt: Optional[str] = None,
        audio: Optional[bool] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        if not prompt:
            return error_response(
                error="Prompt is required",
                error_type="invalid_request",
                provider=self.name,
            )

        cfg = _load_config()
        key_env = _resolve_key_env(cfg)
        api_key = os.environ.get(key_env, "").strip()
        if not api_key:
            return error_response(
                error=(
                    f"{key_env} not set. Configure video_gen.minimax.key_env "
                    f"in config.yaml and set the env var, or run `duckwork tools` "
                    f"-> Video Generation -> MiniMax."
                ),
                error_type="missing_credentials",
                provider=self.name,
            )

        # Determine mode from inputs
        # - image_url only -> I2V (image becomes first frame)
        # - reference_image_urls only -> S2V (subject reference)
        # - neither -> T2V
        if image_url:
            mode = "i2v"
            modality = "image"
        elif reference_image_urls:
            mode = "s2v"
            modality = "image"
        else:
            mode = "t2v"
            modality = "text"

        # Model resolution:
        # 1. Explicit model kwarg (full model ID from tool call)
        # 2. Per-mode config override (model_s2v for S2V)
        # 3. Config default model (for t2v/i2v)
        # 4. Hard-coded default
        if mode == "s2v":
            model_id = (
                model
                or cfg.get("model_s2v")
                or _DEFAULT_MODEL_S2V
            )
        else:
            model_id = (
                model
                or cfg.get("model")
                or _DEFAULT_MODEL
            )

        # Clamp duration: MiniMax supports 6 or 10 seconds.
        # Default to 6. If user asks for >6 and <=10, use 10. Otherwise 6.
        dur = duration or 6
        if dur >= 10:
            dur = 10
        else:
            dur = 6

        # Resolution: config > explicit kwarg (non-default) > model default.
        # The tool layer always passes resolution=DEFAULT_RESOLUTION ("720p")
        # even when the user didn't pick one, so we only honour the kwarg when
        # it differs from the default.  This prevents sending "720P" to models
        # like Hailuo-2.3 that only support 768P/1080P.
        res = cfg.get("resolution", "")
        if not res and isinstance(resolution, str) and resolution.strip() and resolution.strip() != DEFAULT_RESOLUTION:
            res = resolution.strip()
        # Normalize to MiniMax format (e.g. "720p" -> "720P")
        if res:
            res = res.upper()
            if not res.endswith("P"):
                res = res + "P"
        if not res:
            # Hailuo-2.3/02 default to 768P, older models to 720P
            if "Hailuo" in model_id:
                res = "768P"
            else:
                res = "720P"

        # Build request payload
        payload: Dict[str, Any] = {
            "model": model_id,
            "prompt": prompt,
            "duration": dur,
            "resolution": res,
        }

        # prompt_optimizer: default true, configurable
        prompt_opt = cfg.get("prompt_optimizer")
        if prompt_opt is not None:
            payload["prompt_optimizer"] = bool(prompt_opt)

        # Mode-specific fields
        if mode == "i2v" and image_url:
            payload["first_frame_image"] = _normalize_source(image_url)
        elif mode == "s2v" and reference_image_urls:
            # S2V uses subject_reference array with nested image arrays
            refs = []
            for src in reference_image_urls:
                refs.append({
                    "type": "character",
                    "image": [_normalize_source(src)],
                })
            payload["subject_reference"] = refs

        base = _resolve_api(cfg)
        submit_url = f"{base}/v1/video_generation"

        try:
            import requests

            # Step 1: Submit async task
            resp = requests.post(
                submit_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            submit_data = resp.json()
        except Exception as exc:
            logger.debug("MiniMax video submit failed", exc_info=True)
            return error_response(
                error=f"MiniMax video submit failed: {exc}",
                error_type="api_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        # Check for API-level errors
        base_resp = submit_data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            return error_response(
                error=f"MiniMax error: {base_resp.get('status_msg', 'unknown error')} (code: {status_code})",
                error_type="api_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        task_id = submit_data.get("task_id")
        if not task_id:
            return error_response(
                error="MiniMax did not return a task_id",
                error_type="empty_response",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        # Step 2: Poll until terminal
        query_url = f"{base}/v1/query/video_generation"
        deadline = time.monotonic() + _POLL_DEADLINE_S
        terminal_states = {"Success", "Fail"}
        task_status = "Preparing"
        poll_data: Dict[str, Any] = {}

        try:
            while task_status not in terminal_states:
                if time.monotonic() >= deadline:
                    return error_response(
                        error=f"Video generation timed out after {int(_POLL_DEADLINE_S)}s (task {task_id})",
                        error_type="timeout",
                        provider=self.name,
                        model=model_id,
                        prompt=prompt,
                    )
                time.sleep(_POLL_INTERVAL_S)
                poll_resp = requests.get(
                    query_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"task_id": task_id},
                    timeout=30,
                )
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
                task_status = poll_data.get("status", "Preparing")
        except Exception as exc:
            logger.debug("MiniMax video poll failed", exc_info=True)
            return error_response(
                error=f"MiniMax video polling failed: {exc}",
                error_type="api_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        if task_status != "Success":
            return error_response(
                error=f"Video generation {task_status}",
                error_type="generation_failed",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        # Step 3: Get file_id from poll response, retrieve download URL
        file_id = poll_data.get("file_id")
        if not file_id:
            return error_response(
                error="MiniMax task succeeded but no file_id in response",
                error_type="empty_response",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        # Retrieve the download URL via the file retrieve endpoint
        retrieve_url = f"{base}/v1/files/retrieve"
        try:
            retrieve_resp = requests.get(
                retrieve_url,
                headers={"Authorization": f"Bearer {api_key}"},
                params={"file_id": file_id},
                timeout=30,
            )
            retrieve_resp.raise_for_status()
            retrieve_data = retrieve_resp.json()
        except Exception as exc:
            logger.debug("MiniMax file retrieve failed", exc_info=True)
            return error_response(
                error=f"MiniMax file retrieve failed: {exc}",
                error_type="api_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        retrieve_base_resp = retrieve_data.get("base_resp", {})
        if retrieve_base_resp.get("status_code", 0) != 0:
            return error_response(
                error=f"MiniMax file retrieve error: {retrieve_base_resp.get('status_msg', 'unknown')}",
                error_type="api_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        file_info = retrieve_data.get("file", {})
        download_url = file_info.get("download_url")
        if not download_url:
            return error_response(
                error="MiniMax file retrieve succeeded but no download_url",
                error_type="empty_response",
                provider=self.name,
                model=model_id,
                prompt=prompt,
            )

        # Step 4: Download and cache locally (URLs are ephemeral)
        short = model_id.replace(".", "_").replace("-", "_")
        try:
            saved_path = save_url_video(download_url, prefix=f"minimax_{short}")
            video_ref = str(saved_path)
        except Exception as exc:
            logger.debug("MiniMax: caching video URL failed (%s); returning URL", exc)
            video_ref = download_url

        return success_response(
            video=video_ref,
            model=model_id,
            prompt=prompt,
            modality=modality,
            aspect_ratio=aspect_ratio,
            duration=dur,
            provider=self.name,
            extra={
                "task_id": task_id,
                "file_id": str(file_id),
                "resolution": res,
            },
        )


def register(ctx) -> None:
    """Plugin entry point -- wire MiniMaxVideoGenProvider into the registry."""
    ctx.register_video_gen_provider(MiniMaxVideoGenProvider())