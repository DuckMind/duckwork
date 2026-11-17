"""MiniMax image generation backend.

Exposes MiniMax's image-01 models through the MiniMax image generation
API as an ImageGenProvider.

Supports both text-to-image (image-01) and image-to-image (image-01-live)
using the subject_reference field for character/scene references.

Configuration (config.yaml):

    image_gen:
      provider: minimax
      minimax:
        api: https://api.minimax.io
        key_env: MINIMAX_API_KEY
        model: image-01            # optional default model

All keys are optional. Defaults:
  - api:     https://api.minimax.io
  - key_env: MINIMAX_API_KEY
  - model:   image-01

API: POST {api}/v1/image_generation
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    normalize_reference_images,
    resolve_aspect_ratio,
    save_url_image,
    success_response,
)

logger = logging.getLogger(__name__)

# MiniMax uses W:H ratio strings (e.g. "16:9").
# Duckwork aspect_ratio values: "landscape", "square", "portrait".
_ASPECT_RATIOS = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
}

_MODELS = [
    {
        "id": "image-01",
        "display": "Image-01",
        "speed": "~5s",
        "strengths": "Text-to-image generation",
        "price": "PAYG / token plan",
    },
    {
        "id": "image-01-live",
        "display": "Image-01 Live",
        "speed": "~10s",
        "strengths": "Image-to-image with subject reference",
        "price": "PAYG / token plan",
    },
]

# Defaults when config keys are absent.
_DEFAULT_API = "https://api.minimax.io"
_DEFAULT_KEY_ENV = "MINIMAX_API_KEY"

# Max file size for base64 inline encoding (10 MB).
_MAX_INLINE_BYTES = 10 * 1024 * 1024


def _to_data_uri(path: str) -> str:
    """Convert a local image file to a base64 data URI.

    MiniMax accepts data URIs in the ``image_file`` field of
    subject_reference entries.  Local paths are detected and converted
    automatically so callers can pass file paths directly.

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


def _load_config() -> Dict[str, Any]:
    """Read ``image_gen.minimax`` from config.yaml."""
    try:
        from duckwork_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        mm = section.get("minimax") if isinstance(section, dict) else None
        return mm if isinstance(mm, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen.minimax config: %s", exc)
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


class MiniMaxImageGenProvider(ImageGenProvider):
    """MiniMax image generation backend.

    Uses the MiniMax image generation API for both text-to-image
    (image-01) and image-to-image (image-01-live) generation.
    """

    @property
    def name(self) -> str:
        return "minimax"

    @property
    def display_name(self) -> str:
        return "MiniMax"

    def is_available(self) -> bool:
        cfg = _load_config()
        key_env = _resolve_key_env(cfg)
        return bool(os.environ.get(key_env, "").strip())

    def list_models(self) -> List[Dict[str, Any]]:
        return list(_MODELS)

    def default_model(self) -> Optional[str]:
        return "image-01"

    def capabilities(self) -> Dict[str, Any]:
        return {"modalities": ["text", "image"], "max_reference_images": 1}

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "MiniMax",
            "badge": "api-key",
            "tag": "Image-01 models via MiniMax platform",
            "env_vars": [
                {
                    "key": "MINIMAX_API_KEY",
                    "prompt": "MiniMax API key",
                    "url": "https://platform.minimax.io/user-center/basic-information/interface-key",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider=self.name,
                aspect_ratio=aspect,
            )

        # MiniMax prompt max length is 1500 characters.
        if len(prompt) > 1500:
            prompt = prompt[:1500]

        cfg = _load_config()
        key_env = _resolve_key_env(cfg)
        api_key = os.environ.get(key_env, "").strip()
        if not api_key:
            return error_response(
                error=(
                    f"{key_env} not set. Configure image_gen.minimax.key_env "
                    f"in config.yaml and set the env var, or run `duckwork tools` "
                    f"-> Image Generation -> MiniMax."
                ),
                error_type="auth_required",
                provider=self.name,
                aspect_ratio=aspect,
            )

        # Model selection: explicit kwarg > config > default
        model_id = (
            kwargs.get("model")
            or cfg.get("model")
            or self.default_model()
        )

        # Determine modality from source images
        sources: List[str] = []
        if image_url:
            sources.append(_normalize_source(image_url))
        sources.extend(
            _normalize_source(s)
            for s in (normalize_reference_images(reference_image_urls) or [])
        )
        modality = "image" if sources else "text"

        # Image-to-image requires image-01-live model
        if modality == "image" and model_id == "image-01":
            model_id = "image-01-live"

        aspect_str = _ASPECT_RATIOS.get(aspect, _ASPECT_RATIOS["square"])

        # Build the MiniMax image generation request.
        payload: Dict[str, Any] = {
            "model": model_id,
            "prompt": prompt,
            "aspect_ratio": aspect_str,
            "response_format": "url",
            "n": 1,
        }

        # For i2i, add subject_reference entries
        if sources:
            payload["subject_reference"] = [
                {
                    "type": "character",
                    "image_file": src,
                }
                for src in sources
            ]

        base = _resolve_api(cfg)
        url = f"{base}/v1/image_generation"

        try:
            import requests

            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("MiniMax image generation failed", exc_info=True)
            return error_response(
                error=f"MiniMax API request failed: {exc}",
                error_type="api_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Check for API-level errors
        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            return error_response(
                error=f"MiniMax error: {base_resp.get('status_msg', 'unknown error')} (code: {status_code})",
                error_type="api_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Extract image URL from response.
        image_ref: Optional[str] = None
        try:
            image_urls = data["data"]["image_urls"]
            if image_urls and len(image_urls) > 0:
                image_ref = image_urls[0]
        except (KeyError, IndexError, TypeError) as exc:
            return error_response(
                error=f"Unexpected MiniMax response structure: {exc}",
                error_type="parse_error",
                provider=self.name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        if not image_ref:
            return error_response(
                error="MiniMax response contained no image URL",
                error_type="empty_response",
                provider=self.name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Cache the image locally -- MiniMax URLs expire in 24 hours.
        short = model_id.replace(".", "_")
        try:
            saved_path = save_url_image(image_ref, prefix=f"minimax_{short}")
            image_ref = str(saved_path)
        except Exception as exc:
            logger.debug(
                "MiniMax: caching image URL failed (%s); returning URL", exc
            )

        return success_response(
            image=image_ref,
            model=model_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider=self.name,
            modality=modality,
            extra={"aspect_ratio": aspect_str},
        )


def register(ctx) -> None:
    """Plugin entry point -- wire MiniMaxImageGenProvider into the registry."""
    ctx.register_image_gen_provider(MiniMaxImageGenProvider())