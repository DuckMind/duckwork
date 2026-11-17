# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Parcel API client: bounded HTTP, local rate budget, and an on-disk cache.

Parcel's external API is small and strictly rate limited (deliveries: 20 requests an
hour; add-delivery: 20 a day, failures included). Its deliveries endpoint serves a
cached copy from Parcel's server, so polling it harder never yields fresher data.
Everything here exists to avoid wasting those requests.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

PLUGIN_NAME = "parcel-deliveries"
API_BASE = "https://api.parcel.app/external"
CARRIERS_URL = f"{API_BASE}/supported_carriers.json"
ENV_KEY = "PARCEL_API_KEY"

DELIVERIES_PER_HOUR = 20
ADDS_PER_DAY = 20
DEFAULT_CACHE_SECONDS = 600
CARRIERS_CACHE_SECONDS = 24 * 3600
MAX_DELIVERIES_BYTES = 5_000_000
MAX_CARRIERS_BYTES = 1_000_000
TIMEOUT_SECONDS = 15

STATUS_LABELS = {
    0: "delivered",
    1: "stalled",
    2: "in_transit",
    3: "ready_for_pickup",
    4: "out_for_delivery",
    5: "not_found",
    6: "delivery_attempt_failed",
    7: "exception",
    8: "label_created",
}
STATUS_DESCRIPTIONS = {
    "delivered": "Delivered.",
    "stalled": "No updates for a long time; Parcel expects none.",
    "in_transit": "In transit.",
    "ready_for_pickup": "Waiting for the recipient to pick it up.",
    "out_for_delivery": "Out for delivery.",
    "not_found": "The carrier doesn't know this tracking number (yet).",
    "delivery_attempt_failed": "A delivery attempt failed.",
    "exception": "Delivery exception: something needs attention.",
    "label_created": "Carrier has the shipping info but not the package yet.",
}

_TRACKING_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/-]{2,63}$")
_CARRIER_RE = re.compile(r"^[a-z0-9_]{2,32}$")
_LANGUAGE_RE = re.compile(r"^[a-z]{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}$")


class ParcelError(Exception):
    """A user-presentable failure. Never carries the API key or a raw response body."""

    def __init__(self, message: str, *, code: str = "error"):
        super().__init__(message)
        self.code = code


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise ParcelError("Parcel answered with a redirect; refused to forward the API key.",
                          code="redirect")


def _default_transport():
    return urllib.request.build_opener(_NoRedirect()).open


def _clean_text(value: Any, limit: int = 200) -> str:
    text = "".join(ch for ch in str(value) if ch.isprintable())
    return text[:limit]


def resolve_api_key() -> Optional[str]:
    """Read the key through Duckwork' profile-scoped secret lookup when available."""
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return os.environ.get(ENV_KEY) or None
    return get_secret(ENV_KEY) or None


def default_data_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir
        return plugin_data_dir(PLUGIN_NAME)
    except ImportError:
        home = os.environ.get("DUCKWORK_HOME") or str(Path.home() / ".duckwork")
        path = Path(home) / "plugin-data" / PLUGIN_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path


class _StateFile:
    """Small JSON state file, written atomically with 0600 permissions."""

    _lock = threading.Lock()

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".state-", dir=str(self.path.parent))
        try:
            if hasattr(os, "fchmod"):  # not on Windows
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


class ParcelClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        data_dir: Optional[Path] = None,
        transport: Optional[Callable] = None,
        clock: Callable[[], float] = time.time,
        key_resolver: Callable[[], Optional[str]] = resolve_api_key,
    ):
        self._api_key = api_key
        self._key_resolver = key_resolver
        self._transport = transport or _default_transport()
        self._clock = clock
        self._state = _StateFile(Path(data_dir or default_data_dir()) / "state.json")

    # ── HTTP ────────────────────────────────────────────────────────────────

    def _key(self) -> str:
        key = self._api_key or self._key_resolver()
        if not key:
            raise ParcelError(
                f"{ENV_KEY} is not set. Generate a key at https://web.parcelapp.net "
                "(Parcel Premium) and save it as a secret.", code="missing_key")
        return key

    def _http(self, url: str, *, method: str = "GET", body: Optional[dict] = None,
              send_key: bool = True, max_bytes: int = MAX_DELIVERIES_BYTES) -> Any:
        headers = {"Accept": "application/json", "User-Agent": "duckwork-parcel-deliveries"}
        if send_key:
            headers["api-key"] = self._key()
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._transport(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read(max_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from None
        except ParcelError:
            raise
        except (urllib.error.URLError, OSError, TimeoutError):
            raise ParcelError("Couldn't reach Parcel. Check the network and try again later.",
                              code="network") from None
        if len(raw) > max_bytes:
            raise ParcelError("Parcel's response was larger than expected; refused it.",
                              code="too_large")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ParcelError("Parcel returned something that isn't JSON.", code="bad_json") from None

    @staticmethod
    def _http_error(exc: urllib.error.HTTPError) -> ParcelError:
        detail = ""
        try:
            payload = json.loads(exc.read(4096) or b"{}")
            if isinstance(payload, dict) and payload.get("error_message"):
                detail = _clean_text(payload["error_message"])
        except Exception:
            detail = ""
        if exc.code == 429 or "limit" in detail.lower():
            return ParcelError("Parcel's rate limit is used up. Try again later.", code="rate_limited")
        if exc.code in (401, 403):
            hint = f" Parcel said: {detail}." if detail else ""
            return ParcelError(
                "Parcel rejected the API key. Make sure it's current and the account has "
                f"Parcel Premium.{hint}", code="auth")
        suffix = f": {detail}" if detail else ""
        return ParcelError(f"Parcel request failed (HTTP {exc.code}){suffix}", code="http")

    # ── Local rate budget ───────────────────────────────────────────────────

    def _recent_calls(self, state: dict, bucket: str, window: float) -> list:
        now = self._clock()
        calls = [t for t in state.get("calls", {}).get(bucket, [])
                 if isinstance(t, (int, float)) and now - t < window]
        state.setdefault("calls", {})[bucket] = calls
        return calls

    def budget(self) -> dict:
        state = self._state.load()
        hour = self._recent_calls(state, "deliveries", 3600)
        day = self._recent_calls(state, "add", 86400)
        return {
            "deliveries_requests_left_this_hour": max(0, DELIVERIES_PER_HOUR - len(hour)),
            "add_requests_left_today": max(0, ADDS_PER_DAY - len(day)),
            "note": "Counts only this host's requests; other apps using the same key share the limit.",
        }

    def _spend(self, bucket: str, window: float, limit: int) -> None:
        with _StateFile._lock:
            state = self._state.load()
            calls = self._recent_calls(state, bucket, window)
            if len(calls) >= limit:
                wait = int(window - (self._clock() - min(calls))) + 1
                raise ParcelError(
                    f"This host already used Parcel's limit ({limit} per "
                    f"{'hour' if window == 3600 else 'day'}). Try again in about "
                    f"{max(1, wait // 60)} min.", code="rate_limited")
            calls.append(self._clock())
            self._state.save(state)

    # ── Deliveries ──────────────────────────────────────────────────────────

    def deliveries(self, filter_mode: str = "active", *, max_age: float = DEFAULT_CACHE_SECONDS,
                   refresh: bool = False) -> dict:
        """Return ``{"deliveries": [...], "fetched_at": ts, "from_cache": bool, "stale": bool}``."""
        if filter_mode not in ("active", "recent"):
            raise ParcelError("filter must be 'active' or 'recent'.", code="invalid")
        now = self._clock()
        cached = self._state.load().get("cache", {}).get(filter_mode)
        if (not refresh and isinstance(cached, dict)
                and now - float(cached.get("fetched_at", 0)) < max_age):
            return {**cached, "from_cache": True, "stale": False}
        try:
            self._spend("deliveries", 3600, DELIVERIES_PER_HOUR)
            url = f"{API_BASE}/deliveries/?" + urllib.parse.urlencode({"filter_mode": filter_mode})
            payload = self._http(url)
            if not isinstance(payload, dict):
                raise ParcelError("Parcel returned an unexpected response.", code="bad_shape")
            if not payload.get("success"):
                message = _clean_text(payload.get("error_message") or "unknown error")
                code = "rate_limited" if "limit" in message.lower() else "api"
                raise ParcelError(f"Parcel said: {message}", code=code)
            raw = payload.get("deliveries") or []
            if not isinstance(raw, list):
                raise ParcelError("Parcel's delivery list was malformed.", code="bad_shape")
        except ParcelError as exc:
            # A rate limit or outage shouldn't hide what we already know.
            if isinstance(cached, dict) and exc.code in ("rate_limited", "network", "http"):
                return {**cached, "from_cache": True, "stale": True, "warning": str(exc)}
            raise
        entry = {"fetched_at": now, "deliveries": [d for d in raw if isinstance(d, dict)]}
        with _StateFile._lock:
            state = self._state.load()
            state.setdefault("cache", {})[filter_mode] = entry
            self._state.save(state)
        return {**entry, "from_cache": False, "stale": False}

    def cached_tracking_numbers(self) -> set:
        numbers = set()
        for entry in (self._state.load().get("cache") or {}).values():
            for item in (entry or {}).get("deliveries", []):
                if isinstance(item, dict) and item.get("tracking_number"):
                    numbers.add(normalize_tracking(str(item["tracking_number"])))
        return numbers

    def forget_cache(self) -> None:
        with _StateFile._lock:
            state = self._state.load()
            state.pop("cache", None)
            self._state.save(state)

    # ── Carriers ────────────────────────────────────────────────────────────

    def carriers(self) -> dict:
        state = self._state.load()
        cached = state.get("carriers")
        now = self._clock()
        if isinstance(cached, dict) and now - float(cached.get("fetched_at", 0)) < CARRIERS_CACHE_SECONDS:
            return cached.get("data") or {}
        try:
            data = self._http(CARRIERS_URL, send_key=False, max_bytes=MAX_CARRIERS_BYTES)
            if not isinstance(data, dict):
                raise ParcelError("Parcel's carrier list was malformed.", code="bad_shape")
        except ParcelError:
            if isinstance(cached, dict) and cached.get("data"):
                return cached["data"]
            raise
        clean = {}
        for code, info in data.items():
            if isinstance(code, str) and _CARRIER_RE.match(code) and isinstance(info, dict):
                clean[code] = {
                    "name": _clean_text(info.get("name") or code, 80),
                    "extra_required": bool(info.get("extra_required")),
                    "name_variations": [_clean_text(v, 80) for v in info.get("name_variations") or []
                                        if isinstance(v, str)][:10],
                }
        with _StateFile._lock:
            state = self._state.load()
            state["carriers"] = {"fetched_at": now, "data": clean}
            self._state.save(state)
        return clean

    # ── Add ─────────────────────────────────────────────────────────────────

    def add_delivery(self, *, tracking_number: str, carrier_code: str, description: str,
                     postcode: str = "", email: str = "", language: str = "",
                     send_push_confirmation: bool = False) -> dict:
        body = {
            "tracking_number": tracking_number,
            "carrier_code": carrier_code,
            "description": description,
            "send_push_confirmation": bool(send_push_confirmation),
        }
        if postcode:
            body["postcode"] = postcode
        if email:
            body["email"] = email
        if language:
            body["language"] = language
        self._spend("add", 86400, ADDS_PER_DAY)
        payload = self._http(f"{API_BASE}/add-delivery/", method="POST", body=body)
        if not isinstance(payload, dict):
            raise ParcelError("Parcel returned an unexpected response.", code="bad_shape")
        if not payload.get("success"):
            message = _clean_text(payload.get("error_message") or "unknown error")
            raise ParcelError(f"Parcel didn't add it: {message}", code="api")
        # Make the next read show the new delivery instead of a cached list without it.
        self.forget_cache()
        return {"added": True}


def normalize_tracking(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


def validate_add_args(args: dict, carriers: Optional[dict]) -> dict:
    """Check everything locally first: a rejected add still costs one of 20 daily requests."""
    tracking = str(args.get("tracking_number") or "").strip()
    carrier = str(args.get("carrier_code") or "").strip().lower()
    description = _clean_text(str(args.get("description") or "").strip(), 120)
    postcode = _clean_text(str(args.get("postcode") or "").strip(), 20)
    email = str(args.get("email") or "").strip()
    language = str(args.get("language") or "").strip().lower()

    if not _TRACKING_RE.match(tracking):
        raise ParcelError("tracking_number must be 3-64 letters, digits, spaces, dots, dashes or slashes.",
                          code="invalid")
    if not _CARRIER_RE.match(carrier):
        raise ParcelError("carrier_code must be a Parcel carrier code such as 'ups', 'usps', 'fedex' "
                          "or 'amzlus'. Use parcel_carriers to look one up.", code="invalid")
    if not description:
        raise ParcelError("description is required (e.g. 'New running shoes').", code="invalid")
    if email and not _EMAIL_RE.match(email):
        raise ParcelError("email doesn't look like an email address.", code="invalid")
    if language and not _LANGUAGE_RE.match(language):
        raise ParcelError("language must be a two-letter code like 'en'.", code="invalid")
    if carriers and carrier != "pholder":
        info = carriers.get(carrier)
        if info is None:
            raise ParcelError(f"'{carrier}' isn't a Parcel carrier code. Use parcel_carriers to find "
                              "the right one.", code="unknown_carrier")
        if info.get("extra_required") and not (postcode or email):
            raise ParcelError(f"{info.get('name', carrier)} needs a postcode or order email to track. "
                              "Ask for it and pass postcode or email.", code="extra_required")
    return {
        "tracking_number": tracking,
        "carrier_code": carrier,
        "description": description,
        "postcode": postcode,
        "email": email,
        "language": language,
        "send_push_confirmation": bool(args.get("send_push_confirmation", False)),
    }
