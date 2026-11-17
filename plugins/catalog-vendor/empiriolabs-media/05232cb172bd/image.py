"""EmpirioLabs AI backend for Duckwork' ``image_generate`` tool (generation and editing)."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Optional

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    normalize_reference_images,
    resolve_aspect_ratio,
    save_b64_image,
    save_url_image,
    success_response,
)

from . import _api

logger = logging.getLogger(__name__)

ENDPOINT = "POST /v1/images/generations"

# Picked from the live catalog on 2026-10-19 (the lowest-priced featured image model). Used only
# when it is still in the catalog and no other model is configured.
DEFAULT_IMAGE_MODEL = "flux-2-klein-4b"

REQUEST_TIMEOUT_SECONDS = 300.0  # the API holds a sync request for up to about four minutes
JOB_DEADLINE_SECONDS = 600.0
JOB_POLL_SECONDS = 3.0
MAX_LOCAL_IMAGE_BYTES = 20 * 1024 * 1024

# Duckwork' semantic aspect ratios, most preferred catalog value first.
_ASPECT_CHOICES = {
    "landscape": ("16:9", "3:2", "4:3"),
    "square": ("1:1",),
    "portrait": ("9:16", "2:3", "3:4"),
}


def is_image_model(row: dict[str, Any]) -> bool:
    """A text-to-image model on /v1/images/generations that needs nothing but a prompt."""
    return (
        _api.serves(row, ENDPOINT)
        and str(row.get("category") or "image") == "image"
        and _api.required_params(row) <= {"prompt"}
    )


def _reference_param(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return _api.param(row, "image") or _api.param(row, "images")


def _accepts_images(row: Optional[dict[str, Any]]) -> bool:
    return bool(row) and "image" in _api.string_list(row.get("input_modalities")) and _reference_param(row) is not None


def _size_for(aspect: str, sizes: list[str]) -> Optional[str]:
    """The ``WxH`` option that best matches a semantic aspect ratio."""
    parsed = []
    for option in sizes:
        try:
            width, height = (int(part) for part in option.lower().split("x", 1))
        except ValueError:
            continue
        if width > 0 and height > 0:
            parsed.append((width / height, option))
    if aspect == "landscape":
        wide = [item for item in parsed if item[0] > 1.01]
        return max(wide)[1] if wide else None
    if aspect == "portrait":
        tall = [item for item in parsed if item[0] < 0.99]
        return min(tall)[1] if tall else None
    square = [item for item in parsed if 0.99 <= item[0] <= 1.01]
    return square[0][1] if square else None


def _shape_fields(aspect: str, row: Optional[dict[str, Any]]) -> dict[str, str]:
    """``aspect_ratio`` (or ``size``) for the request, limited to values the model declares."""
    if row is None:
        return {"aspect_ratio": _ASPECT_CHOICES[aspect][0]}
    ratios = _api.param_options(row, "aspect_ratio")
    if ratios:
        for choice in _ASPECT_CHOICES[aspect]:
            if choice in ratios:
                return {"aspect_ratio": choice}
        return {}
    size = _size_for(aspect, _api.param_options(row, "size"))
    return {"size": size} if size else {}


def _sniff_image(raw: bytes) -> Optional[str]:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


def _b64_extension(data: str) -> str:
    """File extension for base64 image data, from its first bytes (png when unknown)."""
    try:
        head = base64.b64decode(data[:24])
    except (ValueError, TypeError):
        return "png"
    kind = _sniff_image(head) or "png"
    return "jpg" if kind == "jpeg" else kind


def source_for_api(source: str) -> str:
    """An https/http URL or ``data:image`` URI as is; a local image file inlined as a data URI."""
    value = source.strip()
    if value.lower().startswith(("https://", "http://", "data:image/")):
        return value
    path = Path(value).expanduser()
    if not path.is_file():
        raise ValueError(f"{value!r} is not an https URL, a data:image URI or an existing local image file")
    if path.stat().st_size > MAX_LOCAL_IMAGE_BYTES:
        raise ValueError(f"{path.name} is larger than {MAX_LOCAL_IMAGE_BYTES // (1024 * 1024)} MB")
    raw = path.read_bytes()
    kind = _sniff_image(raw)
    if kind is None:
        raise ValueError(f"{path.name} is not a PNG, JPEG, WebP or GIF image")
    return f"data:image/{kind};base64,{base64.b64encode(raw).decode('ascii')}"


class EmpirioLabsImageGenProvider(ImageGenProvider):
    """``image_gen.provider: empiriolabs``; the model comes from ``image_gen.model`` (set by
    ``duckwork tools``), then ``image_gen.empiriolabs.model``, then the release default."""

    @property
    def name(self) -> str:
        return _api.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return _api.DISPLAY_NAME

    def is_available(self) -> bool:
        return bool(_api.api_key())

    def get_setup_schema(self) -> dict[str, Any]:
        return _api.setup_schema("Image generation and editing with models from the live EmpirioLabs AI catalog")

    def list_models(self) -> list[dict[str, Any]]:
        return _api.catalog_rows_for_picker(_api.catalog(), is_image_model)

    def default_model(self) -> Optional[str]:
        model_id, _row = self._resolve(None)
        return model_id

    def _resolve(self, requested: Optional[str], *, allow_network: bool = True) -> tuple[Optional[str], Optional[dict]]:
        configured = _api.provider_config("image_gen").get("model")
        rows = _api.catalog(allow_network=allow_network)
        return _api.choose_model(rows, is_image_model, DEFAULT_IMAGE_MODEL, requested, configured)

    def capabilities(self) -> dict[str, Any]:
        """Editing is advertised when the selected model accepts input images."""
        _model, row = self._resolve(None)
        if not _accepts_images(row):
            return {"modalities": ["text"], "max_reference_images": 0}
        total = _api.max_count_from_description(_reference_param(row))
        return {"modalities": ["text", "image"], "max_reference_images": max(0, total - 1)}

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        def fail(error: str, error_type: str, model: str = "") -> dict[str, Any]:
            return error_response(
                error=error, error_type=error_type, provider=self.name, model=model, prompt=prompt,
                aspect_ratio=aspect,
            )

        if not prompt:
            return fail("A prompt is required.", "invalid_input")
        key = _api.api_key()
        if not key:
            return fail(
                f"{_api.KEY_ENV} is not set. Create a key at {_api.API_KEYS_URL} and add it with "
                "`duckwork tools` (Image Generation, EmpirioLabs AI) or to your Duckwork .env file.",
                "auth_required",
            )
        model_id, row = self._resolve(kwargs.get("model"))
        if not model_id:
            return fail("No EmpirioLabs AI image model is available right now.", "no_model_available")

        sources = []
        if isinstance(image_url, str) and image_url.strip():
            sources.append(image_url.strip())
        sources.extend(normalize_reference_images(reference_image_urls) or [])
        if row is not None and sources:
            if not _accepts_images(row):
                return fail(
                    f"{model_id} does not accept input images. Choose an image model that supports editing "
                    "with `duckwork tools`, or omit image_url.", "modality_unsupported", model_id,
                )
            sources = sources[: _api.max_count_from_description(_reference_param(row))]
        try:
            inline_sources = [source_for_api(source) for source in sources]
        except (OSError, ValueError) as exc:
            return fail(f"Could not use the source image: {exc}", "invalid_image_url", model_id)

        payload: dict[str, Any] = {"model": model_id, "prompt": prompt, "num_images": 1, "sync": True}
        payload.update(_shape_fields(aspect, row))
        if inline_sources:
            payload["image"] = inline_sources

        try:
            response = _api.request_json(
                "POST", _api.base_url() + "/images/generations", payload=payload, key=key,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            url, b64, _item, job_id = _api.resolve_output(
                response, key=key, deadline_seconds=JOB_DEADLINE_SECONDS, interval_seconds=JOB_POLL_SECONDS,
            )
        except _api.JobTimeout as exc:
            return fail(
                f"The image job {exc.job_id} is still running. Its result will be available from "
                f"GET {_api.job_url(exc.job_id)}.", "timeout", model_id,
            )
        except _api.ApiError as exc:
            status = f" (HTTP {exc.status})" if exc.status else ""
            return fail(f"EmpirioLabs AI image generation failed{status}: {exc.message}", "api_error", model_id)
        if not (url or b64):
            return fail("EmpirioLabs AI returned no image.", "empty_response", model_id)

        prefix = _api.safe_prefix(model_id)
        if b64:
            data = b64.split(",", 1)[1] if b64.startswith("data:") and "," in b64 else b64
            try:
                image = str(save_b64_image(data, prefix=prefix, extension=_b64_extension(data)))
            except Exception as exc:
                return fail(f"Could not save the generated image: {exc}", "io_error", model_id)
        else:
            try:
                image = str(save_url_image(url, prefix=prefix))
            except Exception as exc:  # keep the signed URL when the local copy fails
                logger.debug("EmpirioLabs AI image download failed (%s); returning the URL", exc)
                image = url
        extra: dict[str, Any] = {"image_url": url} if url else {}
        if job_id:
            extra["job_id"] = job_id
        return success_response(
            image=image, model=model_id, prompt=prompt, aspect_ratio=aspect, provider=self.name,
            modality="image" if inline_sources else "text", extra=extra,
        )
