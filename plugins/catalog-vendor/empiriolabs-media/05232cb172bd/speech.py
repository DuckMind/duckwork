"""EmpirioLabs AI backend for Duckwork' ``text_to_speech`` tool."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from agent.tts_provider import DEFAULT_OUTPUT_FORMAT, TTSProvider

from . import _api

logger = logging.getLogger(__name__)

ENDPOINT = "POST /v1/audio/speech"

# Picked from the live catalog on 2026-10-19 (the lowest-priced featured text-to-speech model).
# Used only when it is still in the catalog and no other model is configured.
DEFAULT_TTS_MODEL = "tts-2-flash"

REQUEST_TIMEOUT_SECONDS = 170.0
JOB_DEADLINE_SECONDS = 300.0
JOB_POLL_SECONDS = 2.0
MAX_AUDIO_BYTES = 100 * 1024 * 1024

_FORMAT_PARAMS = ("output_format", "response_format")
_EXTENSIONS = {"mp3": ".mp3", "wav": ".wav", "ogg": ".ogg", "opus": ".ogg", "flac": ".flac"}
_FALLBACK_ORDER = {
    "mp3": ("mp3", "ogg", "opus", "wav", "flac"),
    "ogg": ("ogg", "opus", "mp3", "wav", "flac"),
    "opus": ("opus", "ogg", "mp3", "wav", "flac"),
    "wav": ("wav", "flac", "mp3", "ogg", "opus"),
    "flac": ("flac", "wav", "mp3", "ogg", "opus"),
}
_SENTENCE_END_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def is_tts_model(row: dict[str, Any]) -> bool:
    """A text-to-speech model on /v1/audio/speech with selectable voices that needs only ``input``."""
    return (
        _api.serves(row, ENDPOINT)
        and str(row.get("category") or "audio") == "audio"
        and str(row.get("type") or "tts") == "tts"
        and _api.param(row, "voice") is not None
        and _api.required_params(row) <= {"input"}
    )


def _format_choice(
    requested: str, row: Optional[dict[str, Any]], *, need_mp3: bool,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """``(param_name, wire_value, format)`` for the request; ``format`` is None when the model
    declares no format choice. ``need_mp3`` puts MP3 first: it is the one format whose pieces can
    be joined back to back."""
    order = _FALLBACK_ORDER.get(requested, _FALLBACK_ORDER["mp3"])
    if need_mp3:
        order = ("mp3",) + order
    for name in _FORMAT_PARAMS:
        offered = {option.lower(): option for option in _api.param_options(row, name)}
        if not offered:
            continue
        for fmt in order:
            if fmt in offered:
                return name, offered[fmt], fmt
        return None, None, None
    return None, None, None


def _sniff_audio(data: bytes) -> Optional[str]:
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "mp3"
    return None


def _split_text(text: str, limit: Optional[int]) -> list[str]:
    """Pieces of at most ``limit`` characters, split at sentence ends, then spaces, then anywhere."""
    if not limit or len(text) <= limit:
        return [text]
    pieces: list[str] = []
    current = ""
    for part in _SENTENCE_END_RE.split(text):
        sentence = part.strip()
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit + 1)
            cut = cut if cut > 0 else limit
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) <= limit:
            current = f"{current} {sentence}"
        else:
            if current:
                pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    return pieces or [text]


def _strip_id3(data: bytes) -> bytes:
    """Drop a leading ID3v2 tag so MP3 pieces can be joined into one stream."""
    if len(data) > 10 and data[:3] == b"ID3":
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        footer = 10 if data[5] & 0x10 else 0
        return data[10 + size + footer:]
    return data


class EmpirioLabsTTSProvider(TTSProvider):
    """``tts.provider: empiriolabs``; the model comes from ``tts.model``, then
    ``tts.empiriolabs.model``, then the release default, and the voice from ``tts.voice``, then
    ``tts.empiriolabs.voice``, then the model's default voice."""

    @property
    def name(self) -> str:
        return _api.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return _api.DISPLAY_NAME

    @property
    def voice_compatible(self) -> bool:
        return True

    def is_available(self) -> bool:
        return bool(_api.api_key())

    def get_setup_schema(self) -> dict[str, Any]:
        return _api.setup_schema("Text-to-speech with models and voices from the live EmpirioLabs AI catalog")

    def list_models(self) -> list[dict[str, Any]]:
        return _api.catalog_rows_for_picker(_api.catalog(), is_tts_model)

    def default_model(self) -> Optional[str]:
        model_id, _row = self._resolve(None)
        return model_id

    def list_voices(self) -> list[dict[str, Any]]:
        _model, row = self._resolve(None)
        return [{"id": voice, "display": voice} for voice in _api.param_options(row, "voice")]

    def default_voice(self) -> Optional[str]:
        _model, row = self._resolve(None)
        return self._voice_for(row, None)

    def _resolve(self, requested: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
        configured = _api.provider_config("tts").get("model")
        return _api.choose_model(_api.catalog(), is_tts_model, DEFAULT_TTS_MODEL, requested, configured)

    @staticmethod
    def _voice_for(row: Optional[dict[str, Any]], requested: Optional[str]) -> Optional[str]:
        configured = _api.provider_config("tts").get("voice")
        if row is None:
            return next((v for v in (requested, configured) if isinstance(v, str) and v.strip()), None)
        offered = {voice.lower(): voice for voice in _api.param_options(row, "voice")}
        for candidate in (requested, configured):
            if isinstance(candidate, str) and candidate.strip().lower() in offered:
                return offered[candidate.strip().lower()]
        default = (_api.param(row, "voice") or {}).get("default")
        if isinstance(default, str) and default:
            return default
        return next(iter(offered.values()), None)

    def synthesize(
        self, text: str, output_path: str, *, voice: Optional[str] = None, model: Optional[str] = None,
        speed: Optional[float] = None, format: str = DEFAULT_OUTPUT_FORMAT, **extra: Any,
    ) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError("No text to speak.")
        key = _api.api_key()
        if not key:
            raise RuntimeError(
                f"{_api.KEY_ENV} is not set. Create a key at {_api.API_KEYS_URL} and add it with "
                "`duckwork tools` (Text-to-Speech, EmpirioLabs AI) or to your Duckwork .env file."
            )
        model_id, row = self._resolve(model)
        if not model_id:
            raise RuntimeError("No EmpirioLabs AI text-to-speech model is available right now.")

        limit = (_api.param(row, "input") or {}).get("max")
        limit = int(limit) if isinstance(limit, (int, float)) and not isinstance(limit, bool) and limit > 0 else None
        pieces = _split_text(text, limit)
        requested_format = str(format or DEFAULT_OUTPUT_FORMAT).lower()
        param_name, wire_format, fmt = _format_choice(requested_format, row, need_mp3=len(pieces) > 1)
        if len(pieces) > 1 and fmt != "mp3":
            raise RuntimeError(
                f"The text is longer than {model_id} accepts in one request ({limit} characters). "
                f"Set tts.{_api.PROVIDER_NAME}.max_text_length to {limit} in config.yaml."
            )

        base: dict[str, Any] = {"model": model_id}
        chosen_voice = self._voice_for(row, voice)
        if chosen_voice:
            base["voice"] = chosen_voice
        if param_name and wire_format:
            base[param_name] = wire_format
        speed_spec = _api.param(row, "speed")
        if speed is not None and (speed_spec is not None or row is None):
            value = float(speed)
            if speed_spec is not None:
                low, high = speed_spec.get("min"), speed_spec.get("max")
                if isinstance(low, (int, float)):
                    value = max(value, float(low))
                if isinstance(high, (int, float)):
                    value = min(value, float(high))
            base["speed"] = value

        chunks: list[bytes] = []
        for index, piece in enumerate(pieces):
            audio = self._request_audio({**base, "input": piece}, key)
            chunks.append(_strip_id3(audio) if index and fmt == "mp3" else audio)

        target = Path(output_path)
        extension = _EXTENSIONS.get(_sniff_audio(chunks[0]) or fmt or "")
        if extension and target.suffix.lower() != extension:
            target = target.with_suffix(extension)
        target.write_bytes(b"".join(chunks))
        return str(target)

    @staticmethod
    def _request_audio(payload: dict[str, Any], key: str) -> bytes:
        try:
            response = _api.request_json(
                "POST", _api.base_url() + "/audio/speech", payload=payload, key=key, timeout=REQUEST_TIMEOUT_SECONDS,
            )
            url, b64, _item, _job = _api.resolve_output(
                response, key=key, deadline_seconds=JOB_DEADLINE_SECONDS, interval_seconds=JOB_POLL_SECONDS,
            )
            if b64:
                return _api.decode_b64(b64)
            if url:
                return _api.download(url, max_bytes=MAX_AUDIO_BYTES)
        except _api.ApiError as exc:
            status = f" (HTTP {exc.status})" if exc.status else ""
            raise RuntimeError(f"EmpirioLabs AI speech synthesis failed{status}: {exc.message}") from exc
        raise RuntimeError("EmpirioLabs AI returned no audio.")
