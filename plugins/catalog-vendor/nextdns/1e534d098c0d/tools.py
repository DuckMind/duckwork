"""Tool handlers for the NextDNS plugin.

Contract per Duckwork plugin rules: handlers accept (args: dict, **kwargs),
always return a JSON string, and never raise.

Read-only. Every endpoint used is a GET; nothing here changes NextDNS
configuration.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

try:  # package import when loaded as a Duckwork plugin
    from . import settings as _settings_mod
except ImportError:  # direct import when testing standalone
    import settings as _settings_mod

_BASE = "https://api.nextdns.io"
_TIMEOUT_SECONDS = 20
_USER_AGENT = "duckwork-nextdns/1.0 (+https://github.com/DuckMind/duckwork)"

# The API rejects limit < 10 with a 400. Callers routinely ask for fewer, so
# the floor is applied here rather than surfacing an error for it.
_LIMIT_MIN = 10
_LOG_LIMIT_MAX = 1000
_ANALYTICS_LIMIT_MAX = 500

# Log rows are small but numerous; cap what a single call can return so a
# broad query cannot swamp the model's context.
_ROWS_MAX = 200

_ANALYTICS_METRICS = (
    "status", "domains", "reasons", "ips", "devices", "protocols",
    "queryTypes", "ipVersions", "dnssec", "encryption", "destinations",
)


def _api_key() -> str:
    return str(_settings_mod.load().get("api_key") or "").strip()


def _profile(args: dict) -> str:
    """Profile id from the call, falling back to the configured default."""
    explicit = str((args or {}).get("profile") or "").strip()
    return explicit or str(_settings_mod.load().get("profile_id") or "").strip()


def _get(path: str, params: dict | None = None) -> dict:
    """GET an endpoint. Returns the decoded body, or {"error": ...}.

    NextDNS reports problems as a JSON ``errors`` array with a useful detail
    string ("`limit` must be >= 10"). Both the HTTP error body and a 200
    carrying ``errors`` are surfaced verbatim - a caller that cannot see why a
    request failed will guess, and guessing costs a lot of calls.
    """
    if not _api_key():
        return {"error": "NEXTDNS_API_KEY is not set"}
    url = _BASE + path
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    # NextDNS rejects the default Python-urllib User-Agent with 403, so an
    # explicit one is required rather than cosmetic.
    req = urllib.request.Request(
        url,
        headers={"X-Api-Key": _api_key(), "User-Agent": _USER_AGENT, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            payload = json.loads(e.read().decode() or "{}")
            detail = "; ".join(
                f"{x.get('source', {}).get('parameter', '')} {x.get('detail', '')}".strip()
                for x in (payload.get("errors") or [])
            ).strip()
        except Exception:  # noqa: BLE001
            detail = ""
        return {"error": f"HTTP {e.code} from NextDNS API: {detail or e.reason}"}
    except Exception as e:  # noqa: BLE001 - handlers must never raise
        return {"error": f"{type(e).__name__}: {e}"}
    if isinstance(body, dict) and body.get("errors"):
        detail = "; ".join(
            f"{x.get('source', {}).get('parameter', '')} {x.get('detail', '')}".strip()
            for x in body["errors"]
        ).strip()
        return {"error": f"NextDNS API: {detail or json.dumps(body['errors'])[:200]}"}
    return body


_device_cache: dict = {}


def _resolve_device(profile: str, wanted: str) -> str:
    """Map a device name to its NextDNS id.

    The logs endpoint filters on device id, but names are what appear in the
    logs and what a caller will have. An unmatched value is passed through
    unchanged so ids and __UNIDENTIFIED__ still work.
    """
    wanted = str(wanted or "").strip()
    if not wanted or wanted.startswith("__"):
        return wanted
    cached = _device_cache.get(profile)
    if cached is None:
        body = _get(f"/profiles/{profile}/analytics/devices", {"limit": 500})
        cached = {}
        for d in (body.get("data") or []):
            name, did = d.get("name"), d.get("id")
            if name and did:
                cached[str(name).lower()] = did
        _device_cache[profile] = cached
    return cached.get(wanted.lower(), wanted)


def _limit(args: dict, ceiling: int) -> int:
    try:
        want = int(args.get("limit") or _LIMIT_MIN)
    except (TypeError, ValueError):
        want = _LIMIT_MIN
    return max(_LIMIT_MIN, min(want, ceiling))


def _row(entry: dict) -> dict:
    """Trim a log entry to the fields that matter for triage."""
    device = entry.get("device")
    if isinstance(device, dict):
        device = device.get("name") or device.get("id")
    return {
        "timestamp": entry.get("timestamp"),
        "domain": entry.get("domain"),
        "status": entry.get("status") or "default",
        "device": device or "unidentified",
        "reasons": [r.get("name") for r in (entry.get("reasons") or []) if isinstance(r, dict)],
        "protocol": entry.get("protocol"),
        "encrypted": entry.get("encrypted"),
    }


def nextdns_logs(args: dict, **kwargs) -> str:
    """Query the DNS log."""
    profile = _profile(args)
    if not profile:
        return json.dumps({"error": "no profile: set NEXTDNS_PROFILE_ID or pass profile"})
    status = str(args.get("status") or "").strip().lower()
    if status and status not in ("default", "blocked", "allowed", "error"):
        return json.dumps({"error": "status must be one of: default, blocked, allowed, error"})
    params = {
        "limit": _limit(args, _LOG_LIMIT_MAX),
        "search": args.get("search"),
        "status": status or None,
        "device": _resolve_device(profile, args.get("device")) if args.get("device") else None,
        "from": args.get("from"),
        "to": args.get("to"),
        "cursor": args.get("cursor"),
        # raw=true includes every query rather than only navigational ones;
        # triage usually wants the unfiltered picture.
        "raw": "true" if args.get("raw", True) else None,
    }
    body = _get(f"/profiles/{profile}/logs", params)
    if "error" in body:
        return json.dumps(body)
    rows = [_row(r) for r in (body.get("data") or [])][:_ROWS_MAX]
    return json.dumps({
        "profile": profile,
        "count": len(rows),
        "cursor": ((body.get("meta") or {}).get("pagination") or {}).get("cursor"),
        "logs": rows,
    })


def nextdns_blocked(args: dict, **kwargs) -> str:
    """Recently blocked queries with the blocklist that matched."""
    merged = dict(args or {})
    merged["status"] = "blocked"
    return nextdns_logs(merged)


def nextdns_analytics(args: dict, **kwargs) -> str:
    """Aggregate counts: top domains, blocklists, devices, protocols, status."""
    profile = _profile(args)
    if not profile:
        return json.dumps({"error": "no profile: set NEXTDNS_PROFILE_ID or pass profile"})
    metric = str(args.get("metric") or "status").strip()
    if metric not in _ANALYTICS_METRICS:
        return json.dumps({
            "error": f"unknown metric '{metric}'",
            "valid_metrics": list(_ANALYTICS_METRICS),
        })
    body = _get(f"/profiles/{profile}/analytics/{metric}", {
        "limit": _limit(args, _ANALYTICS_LIMIT_MAX),
        "from": args.get("from"),
        "to": args.get("to"),
        "device": _resolve_device(profile, args.get("device")) if args.get("device") else None,
    })
    if "error" in body:
        return json.dumps(body)
    return json.dumps({
        "profile": profile,
        "metric": metric,
        "data": (body.get("data") or [])[:_ANALYTICS_LIMIT_MAX],
    })


def nextdns_profile(args: dict, **kwargs) -> str:
    """Profile settings, including whether logging is on and its retention."""
    profile = _profile(args)
    if not profile:
        # With no profile configured, listing what the key can see is the
        # useful answer rather than an error.
        body = _get("/profiles")
        if "error" in body:
            return json.dumps(body)
        return json.dumps({
            "note": "No default profile configured. Set NEXTDNS_PROFILE_ID to one of these.",
            "profiles": [
                {"id": p.get("id"), "name": p.get("name")} for p in (body.get("data") or [])
            ],
        })
    body = _get(f"/profiles/{profile}")
    if "error" in body:
        return json.dumps(body)
    data = body.get("data") or {}
    settings = data.get("settings") or {}
    logs = settings.get("logs") or {}
    retention = logs.get("retention")
    return json.dumps({
        "profile": profile,
        "name": data.get("name"),
        "logging_enabled": bool(logs.get("enabled")),
        "retention_seconds": retention,
        "retention_days": round(retention / 86400, 1) if isinstance(retention, int) else None,
        "log_location": logs.get("location"),
        "blocklists": [b.get("id") for b in (data.get("privacy") or {}).get("blocklists", [])],
        "note": None if logs.get("enabled") else
        "Logging is disabled for this profile; the log endpoints will return nothing.",
    })
