"""EmpirioLabs AI backend for Duckwork' ``video_generate`` tool (text-to-video and image-to-video)."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from agent.video_gen_provider import (
    COMMON_ASPECT_RATIOS,
    COMMON_RESOLUTIONS,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_RESOLUTION,
    VideoGenProvider,
    error_response,
    save_url_video,
    success_response,
)

from . import _api
from .image import source_for_api

logger = logging.getLogger(__name__)

ENDPOINT = "POST /v1/videos/generations"

# Picked from the live catalog on 2026-10-19 (the lowest-priced featured text-to-video and
# image-to-video model). Used only when it is still in the catalog and no other model is configured.
DEFAULT_VIDEO_MODEL = "hunyuan-video-1-5"

REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_JOB_DEADLINE_SECONDS = 900.0
JOB_POLL_SECONDS = 5.0

_IMAGE_FIELDS = ("image", "image_url")
_AUDIO_FIELDS = ("generate_audio", "generate_audio_switch")
_SECONDS_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*s?\s*$", re.IGNORECASE)
_HEIGHT_RE = re.compile(r"^\s*(\d+)\s*p\s*$", re.IGNORECASE)


def is_video_model(row: dict[str, Any]) -> bool:
    """A model on /v1/videos/generations that takes a text prompt and nothing else is required."""
    return (
        _api.serves(row, ENDPOINT)
        and "text" in (_api.string_list(row.get("input_modalities")) or ["text"])
        and _api.required_params(row) == {"prompt"}
    )


def _accepts_image(row: Optional[dict[str, Any]]) -> bool:
    return bool(row) and "image" in _api.string_list(row.get("input_modalities")) and any(
        _api.param(row, field) for field in _IMAGE_FIELDS
    )


def _audio_field(row: Optional[dict[str, Any]]) -> Optional[str]:
    """The model's native-audio switch, when it has one."""
    return next((field for field in _AUDIO_FIELDS if _api.param(row, field) is not None), None)


def _seconds(value: Any) -> Optional[float]:
    match = _SECONDS_RE.match(str(value))
    return float(match.group(1)) if match else None


def _duration_field(requested: Optional[int], row: Optional[dict[str, Any]]) -> Optional[Any]:
    """The ``duration`` to send: an offered option, or the request clamped to the declared range."""
    spec = _api.param(row, "duration")
    if requested is None or spec is None:
        return None
    options = [option for option in _api.param_options(row, "duration") if _seconds(option) is not None]
    if options:
        return min(options, key=lambda option: (abs(_seconds(option) - requested), _seconds(option)))
    low, high = spec.get("min"), spec.get("max")
    value = float(requested)
    if isinstance(low, (int, float)):
        value = max(value, float(low))
    if isinstance(high, (int, float)):
        value = min(value, float(high))
    return int(value) if float(value).is_integer() else value


def _height(resolution: str) -> Optional[int]:
    text = str(resolution).strip().lower()
    if text in ("2k", "4k"):
        return 1440 if text == "2k" else 2160
    match = _HEIGHT_RE.match(text)
    return int(match.group(1)) if match else None


def _resolution_field(requested: Optional[str], row: Optional[dict[str, Any]]) -> Optional[str]:
    """The requested resolution when offered, else the highest offered one below it, else the lowest."""
    options = _api.param_options(row, "resolution")
    if not requested or not options:
        return None
    if requested in options:
        return requested
    wanted = _height(requested)
    sized = [(height, option) for option in options if (height := _height(option))]
    if wanted is None or not sized:
        return None
    below = [item for item in sized if item[0] <= wanted]
    return max(below)[1] if below else min(sized)[1]


def _duration_bounds(row: Optional[dict[str, Any]]) -> tuple[int, int]:
    spec = _api.param(row, "duration")
    if spec is None:
        return 1, 10
    seconds = [value for option in _api.param_options(row, "duration") if (value := _seconds(option)) is not None]
    if seconds:
        return int(min(seconds)), int(max(seconds))
    low = spec.get("min") if isinstance(spec.get("min"), (int, float)) else 1
    high = spec.get("max") if isinstance(spec.get("max"), (int, float)) else max(int(low), 10)
    return int(low), int(high)


class EmpirioLabsVideoGenProvider(VideoGenProvider):
    """``video_gen.provider: empiriolabs``; the model comes from ``video_gen.model`` (set by
    ``duckwork tools``), then ``video_gen.empiriolabs.model``, then the release default."""

    @property
    def name(self) -> str:
        return _api.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return _api.DISPLAY_NAME

    def is_available(self) -> bool:
        return bool(_api.api_key())

    def get_setup_schema(self) -> dict[str, Any]:
        return _api.setup_schema("Text-to-video and image-to-video with models from the live EmpirioLabs AI catalog")

    def list_models(self) -> list[dict[str, Any]]:
        return _api.catalog_rows_for_picker(_api.catalog(), is_video_model)

    def default_model(self) -> Optional[str]:
        model_id, _row = self._resolve(None)
        return model_id

    def _resolve(self, requested: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
        configured = _api.provider_config("video_gen").get("model")
        return _api.choose_model(_api.catalog(), is_video_model, DEFAULT_VIDEO_MODEL, requested, configured)

    def capabilities(self) -> dict[str, Any]:
        _model, row = self._resolve(None)
        if row is None:
            return super().capabilities()
        low, high = _duration_bounds(row)
        resolutions = [option for option in _api.param_options(row, "resolution") if _height(option)]
        references = _api.param(row, "reference_images")
        return {
            "modalities": ["text", "image"] if _accepts_image(row) else ["text"],
            "aspect_ratios": _api.param_options(row, "aspect_ratio") or list(COMMON_ASPECT_RATIOS),
            "resolutions": resolutions or list(COMMON_RESOLUTIONS),
            "min_duration": low,
            "max_duration": high,
            "supports_audio": _audio_field(row) is not None,
            "supports_negative_prompt": _api.param(row, "negative_prompt") is not None,
            "supports_seed": _api.param(row, "seed") is not None,
            "supports_upscale": False,
            "max_reference_images": _api.max_count_from_description(references) if references else 0,
        }

    def _deadline(self) -> float:
        value = _api.provider_config("video_gen").get("timeout_seconds")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return float(value)
        return DEFAULT_JOB_DEADLINE_SECONDS

    def generate(
        self, prompt: str, *, model: Optional[str] = None, image_url: Optional[str] = None,
        reference_image_urls: Optional[list[str]] = None, duration: Optional[int] = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO, resolution: str = DEFAULT_RESOLUTION,
        negative_prompt: Optional[str] = None, audio: Optional[bool] = None,
        seed: Optional[int] = None, **kwargs: Any,
    ) -> dict[str, Any]:
        prompt = (prompt or "").strip()

        def fail(error: str, error_type: str, model_id: str = "") -> dict[str, Any]:
            return error_response(
                error=error, error_type=error_type, provider=self.name, model=model_id, prompt=prompt,
                aspect_ratio=aspect_ratio or "",
            )

        if not prompt:
            return fail("A prompt is required.", "invalid_input")
        key = _api.api_key()
        if not key:
            return fail(
                f"{_api.KEY_ENV} is not set. Create a key at {_api.API_KEYS_URL} and add it with "
                "`duckwork tools` (Video Generation, EmpirioLabs AI) or to your Duckwork .env file.",
                "auth_required",
            )
        model_id, row = self._resolve(model)
        if not model_id:
            return fail("No EmpirioLabs AI video model is available right now.", "no_model_available")

        payload: dict[str, Any] = {"model": model_id, "prompt": prompt}
        modality = "text"
        try:
            if isinstance(image_url, str) and image_url.strip():
                if row is not None and not _accepts_image(row):
                    return fail(
                        f"{model_id} does not animate images. Choose an image-to-video model with "
                        "`duckwork tools`, or omit image_url.", "modality_unsupported", model_id,
                    )
                payload["image"] = source_for_api(image_url)
                modality = "image"
            elif reference_image_urls and _api.param(row, "reference_images") is not None:
                limit = _api.max_count_from_description(_api.param(row, "reference_images"))
                payload["reference_images"] = [source_for_api(ref) for ref in reference_image_urls[:limit]]
                modality = "image"
        except (OSError, ValueError) as exc:
            return fail(f"Could not use the source image: {exc}", "invalid_image_url", model_id)

        if row is None:
            payload["aspect_ratio"] = aspect_ratio
            if duration:
                payload["duration"] = int(duration)
        else:
            if aspect_ratio and aspect_ratio in _api.param_options(row, "aspect_ratio"):
                payload["aspect_ratio"] = aspect_ratio
            resolution_value = _resolution_field(resolution, row)
            if resolution_value:
                payload["resolution"] = resolution_value
            duration_value = _duration_field(duration, row)
            if duration_value is not None:
                payload["duration"] = duration_value
            if negative_prompt and _api.param(row, "negative_prompt") is not None:
                payload["negative_prompt"] = negative_prompt
            audio_field = _audio_field(row)
            if audio is not None and audio_field:
                payload[audio_field] = bool(audio)
            if seed is not None and _api.param(row, "seed") is not None:
                payload["seed"] = int(seed)

        try:
            response = _api.request_json(
                "POST", _api.base_url() + "/videos/generations", payload=payload, key=key,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            url, _b64, item, job_id = _api.resolve_output(
                response, key=key, deadline_seconds=self._deadline(), interval_seconds=JOB_POLL_SECONDS,
            )
        except _api.JobTimeout as exc:
            minutes = int(self._deadline() // 60)
            return fail(
                f"The video job {exc.job_id} is still running after {minutes} minutes and keeps running. "
                f"Its result will be available from GET {_api.job_url(exc.job_id)}.", "timeout", model_id,
            )
        except _api.ApiError as exc:
            status = f" (HTTP {exc.status})" if exc.status else ""
            return fail(f"EmpirioLabs AI video generation failed{status}: {exc.message}", "api_error", model_id)
        if not url:
            return fail("EmpirioLabs AI returned no video URL.", "empty_response", model_id)

        try:
            video = str(save_url_video(url, prefix=_api.safe_prefix(model_id)))
        except Exception as exc:  # keep the signed URL when the local copy fails
            logger.debug("EmpirioLabs AI video download failed (%s); returning the URL", exc)
            video = url
        extra: dict[str, Any] = {"video_url": url}
        if job_id:
            extra["job_id"] = job_id
        seconds = _seconds(item.get("duration")) if item.get("duration") is not None else None
        duration_out = int(seconds) if seconds else int(_seconds(payload.get("duration", 0)) or 0)
        return success_response(
            video=video, model=model_id, prompt=prompt, modality=modality,
            aspect_ratio=str(payload.get("aspect_ratio") or aspect_ratio or ""), duration=duration_out,
            provider=self.name, extra=extra,
        )
