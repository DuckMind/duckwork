"""Tool schemas and handlers. Handlers always return a JSON string and never raise."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .client import (
    STATUS_DESCRIPTIONS,
    STATUS_LABELS,
    ParcelClient,
    ParcelError,
    _clean_text,
    normalize_tracking,
    validate_add_args,
)

MAX_EVENTS = 25
MAX_DELIVERIES = 100

DELIVERIES_SCHEMA = {
    "name": "parcel_deliveries",
    "description": (
        "List the user's package deliveries from the Parcel app (parcelapp.net): status, "
        "expected delivery date, and the latest tracking events. Use for 'where's my package', "
        "'what's arriving today', or before adding a delivery to check it isn't already tracked. "
        "Parcel allows only 20 reads an hour, so results are cached for 10 minutes; set refresh "
        "only when the user explicitly wants the newest data. Parcel's server refreshes tracking "
        "on its own schedule, so refreshing more often never makes data fresher."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "enum": ["active", "recent"],
                "description": "'active' (default): deliveries still on the way. 'recent': also "
                               "recently delivered ones.",
            },
            "tracking_number": {
                "type": "string",
                "description": "Optional: return only the delivery with this tracking number.",
            },
            "include_events": {
                "type": "boolean",
                "description": "Include the full event history (up to 25 events per delivery). "
                               "Default false: only the latest event.",
            },
            "refresh": {
                "type": "boolean",
                "description": "Skip the 10-minute cache. Spends one of Parcel's 20 hourly reads.",
            },
        },
    },
}

ADD_SCHEMA = {
    "name": "parcel_add_delivery",
    "description": (
        "Add a delivery to the user's Parcel app so Parcel tracks it. Only call this when the "
        "user asks to track a specific package. Parcel allows 20 adds a day, failed ones "
        "included, so get the carrier right first: use parcel_carriers to find the carrier "
        "code, and ask the user when the carrier is unclear. New deliveries show 'No data "
        "available' until Parcel's server first updates them."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tracking_number": {"type": "string", "description": "The tracking number."},
            "carrier_code": {
                "type": "string",
                "description": "Parcel carrier code, e.g. 'ups', 'usps', 'fedex', 'amzlus' "
                               "(Amazon US), 'dhl'. 'pholder' adds a placeholder delivery.",
            },
            "description": {
                "type": "string",
                "description": "Short label shown in Parcel, e.g. 'Birthday gift for Sam'.",
            },
            "postcode": {
                "type": "string",
                "description": "Destination postcode, only for carriers that require one.",
            },
            "email": {
                "type": "string",
                "description": "Order email, only for services that require one (e.g. Apple Store).",
            },
            "language": {
                "type": "string",
                "description": "Two-letter language code for tracking text, if the carrier supports it.",
            },
            "send_push_confirmation": {
                "type": "boolean",
                "description": "Have Parcel send a push notification once the delivery is added.",
            },
        },
        "required": ["tracking_number", "carrier_code", "description"],
    },
}

CARRIERS_SCHEMA = {
    "name": "parcel_carriers",
    "description": (
        "Search Parcel's supported carriers to find the carrier_code for parcel_add_delivery. "
        "Matches by code or name (e.g. 'amazon', 'royal mail', 'dhl'). Doesn't use the API key "
        "or any rate limit."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Carrier name or code to look for."},
        },
        "required": ["query"],
    },
}


def _ok(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _fail(exc: Exception) -> str:
    if isinstance(exc, ParcelError):
        return json.dumps({"error": str(exc), "code": exc.code})
    return json.dumps({"error": "Unexpected error in the Parcel plugin.", "code": "internal"})


def _iso(timestamp: Any) -> Optional[str]:
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return None


def _event(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict) or not raw.get("event"):
        return None
    event = {"event": _clean_text(raw["event"], 300), "date": _clean_text(raw.get("date", ""), 60)}
    for key in ("location", "additional"):
        if raw.get(key):
            event[key] = _clean_text(raw[key], 300)
    return event


def summarize_delivery(raw: dict, carriers: dict, include_events: bool) -> dict:
    """Turn one Parcel delivery into a compact, model-friendly record. Unknown fields are dropped."""
    code = raw.get("status_code")
    status = STATUS_LABELS.get(code, "unknown") if isinstance(code, int) else "unknown"
    carrier_code = _clean_text(raw.get("carrier_code", ""), 32)
    events = [e for e in (_event(item) for item in (raw.get("events") or [])[:MAX_EVENTS]) if e]
    item = {
        "description": _clean_text(raw.get("description", ""), 200),
        "tracking_number": _clean_text(raw.get("tracking_number", ""), 64),
        "carrier_code": carrier_code,
        "carrier": (carriers.get(carrier_code) or {}).get("name", carrier_code),
        "status": status,
        "status_text": STATUS_DESCRIPTIONS.get(status, "Unknown status."),
    }
    # Parcel gives the date as the carrier wrote it, plus a UTC timestamp only when it has a timezone.
    expected = {
        "date": _clean_text(raw["date_expected"], 60) if raw.get("date_expected") else None,
        "window_end": _clean_text(raw["date_expected_end"], 60) if raw.get("date_expected_end") else None,
        "utc": _iso(raw.get("timestamp_expected")),
        "utc_window_end": _iso(raw.get("timestamp_expected_end")),
    }
    expected = {k: v for k, v in expected.items() if v}
    if expected:
        item["expected"] = expected
    if events:
        item["latest_event"] = events[0]
        if include_events:
            item["events"] = events
    return item


def _carriers_or_empty(client: ParcelClient) -> dict:
    try:
        return client.carriers()
    except ParcelError:
        return {}


def handle_deliveries(client: ParcelClient, args: dict) -> str:
    try:
        filter_mode = str(args.get("filter") or "active")
        result = client.deliveries(filter_mode, refresh=bool(args.get("refresh")))
        carriers = _carriers_or_empty(client)
        wanted = args.get("tracking_number")
        raw = result["deliveries"]
        if wanted:
            key = normalize_tracking(str(wanted))
            raw = [d for d in raw if normalize_tracking(str(d.get("tracking_number", ""))) == key]
        items = [summarize_delivery(d, carriers, bool(args.get("include_events")))
                 for d in raw[:MAX_DELIVERIES]]
        payload = {
            "filter": filter_mode,
            "count": len(items),
            "deliveries": items,
            "fetched_at": _iso(result["fetched_at"]),
            "from_cache": result["from_cache"],
        }
        if result.get("stale"):
            payload["stale"] = True
            payload["warning"] = result.get("warning")
        if wanted and not items:
            payload["note"] = (f"No {filter_mode} delivery with that tracking number. Try "
                               "filter 'recent' if it was already delivered.")
        return _ok(payload)
    except Exception as exc:  # noqa: BLE001 - handlers must never raise
        return _fail(exc)


def handle_add(client: ParcelClient, args: dict) -> str:
    try:
        carriers = _carriers_or_empty(client)
        clean = validate_add_args(args, carriers)
        if normalize_tracking(clean["tracking_number"]) in client.cached_tracking_numbers():
            return _ok({"added": False, "already_tracked": True,
                        "note": "Parcel already tracks this number; nothing was sent."})
        client.add_delivery(**clean)
        carrier = (carriers.get(clean["carrier_code"]) or {}).get("name", clean["carrier_code"])
        return _ok({
            "added": True,
            "tracking_number": clean["tracking_number"],
            "carrier": carrier,
            "description": clean["description"],
            "note": "Parcel shows 'No data available' until its server first updates this delivery.",
            "adds_left_today": client.budget()["add_requests_left_today"],
        })
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


def handle_carriers(client: ParcelClient, args: dict) -> str:
    try:
        query = str(args.get("query") or "").strip().lower()
        if not query:
            raise ParcelError("query is required.", code="invalid")
        matches = []
        for code, info in client.carriers().items():
            names = [info.get("name", "")] + list(info.get("name_variations") or [])
            if query == code or any(query in n.lower() for n in names) or query in code:
                matches.append({"carrier_code": code, "name": info.get("name", code),
                                "needs_postcode_or_email": bool(info.get("extra_required"))})
        matches.sort(key=lambda m: (m["carrier_code"] != query, m["name"]))
        return _ok({"query": query, "matches": matches[:25], "total_matches": len(matches)})
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


def format_for_command(raw_json: str) -> str:
    """Plain-text summary for the /parcel slash command."""
    data = json.loads(raw_json)
    if "error" in data:
        return f"Parcel: {data['error']}"
    if not data["deliveries"]:
        return "Parcel: nothing on the way."
    lines = [f"Parcel: {data['count']} on the way"]
    for d in data["deliveries"]:
        when = (d.get("expected") or {}).get("date")
        status = d["status"].replace("_", " ")
        lines.append(f"• {d['description'] or d['tracking_number']} ({d['carrier']}): {status}"
                     + (f", expected {when}" if when else ""))
    if data.get("stale"):
        lines.append("(cached; Parcel's rate limit is used up)")
    return "\n".join(lines)
