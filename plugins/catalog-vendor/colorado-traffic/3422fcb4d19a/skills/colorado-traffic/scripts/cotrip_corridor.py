#!/usr/bin/env python3
"""Query CDOT COtrip for a Colorado highway corridor. No API key.

Default corridor is I-70 Golden to east Denver: mile points 259-279
(C-470 / US-6 through Quebec Street).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE = "https://api-511x-co.carsprogram.org"
DENVER = ZoneInfo("America/Denver")
CORRIDORS = {
    "i70-golden-denver": {
        "route": "I-70",
        "min_mp": 259.0,
        "max_mp": 279.0,
        "label": "I-70 Golden to east Denver (MP 259-279, C-470 through Quebec)",
    },
    "i70-golden-i25": {
        "route": "I-70",
        "min_mp": 259.0,
        "max_mp": 274.5,
        "label": "I-70 Golden to I-25 (MP 259-274.5)",
    },
}
LAYERS = {
    "incidents": "roadReports",
    "closures": "roadClosures",
    "work": "roadWork",
    "waze": "wazeReports",
    "winter": "winterDriving",
    "chains": "chainLaws",
}
# (positive, negative) for routePositiveBearing. I-70 positive is east.
# I-25 positive is north. Do not hardcode eastbound.
_BEARING = {
    "E": ("eastbound", "westbound"),
    "W": ("westbound", "eastbound"),
    "N": ("northbound", "southbound"),
    "S": ("southbound", "northbound"),
}


def require_features(data: dict, url: str) -> dict:
    if data == {"healthy": True} or "features" not in data:
        body = json.dumps(data)[:120]
        raise SystemExit(f"unexpected payload from {url}: {body!r}")
    return data


def fetch(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DuckworkColoradoTraffic/1.0",
            "content-language": "en",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        body = resp.read()
    return require_features(json.loads(body), url)


def strip_html(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def milepoints(feature: dict) -> list[float]:
    loc = ((feature.get("properties") or {}).get("eventReport") or {}).get("location") or {}
    points = []
    for key in ("primaryPoint", "secondaryPoint"):
        ref = (loc.get(key) or {}).get("linearReference")
        if isinstance(ref, (int, float)):
            points.append(float(ref))
    return points


def direction(feature: dict) -> str:
    loc = ((feature.get("properties") or {}).get("eventReport") or {}).get("location") or {}
    link = loc.get("linkDirection")
    if link == "BOTH_DIRECTIONS":
        return "both"
    pair = _BEARING.get(loc.get("routePositiveBearing") or "")
    if pair and link == "POSITIVE_DIRECTION":
        return pair[0]
    if pair and link == "NEGATIVE_DIRECTION":
        return pair[1]
    return "unknown"


def ms_to_local(ms: int | None) -> str | None:
    if not ms:
        return None
    return (
        datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        .astimezone(DENVER)
        .strftime("%Y-%m-%d %H:%M %Z")
    )


def timing(feature: dict, now_ms: int) -> str:
    er = (feature.get("properties") or {}).get("eventReport") or {}
    windows = er.get("scheduleOccurrences") or []
    if not windows:
        begin = (er.get("beginTime") or {}).get("time")
        if begin and begin > now_ms:
            return "upcoming"
        return "now"
    states = []
    for window in windows:
        start = (window.get("startTime") or {}).get("time")
        end = (window.get("endTime") or {}).get("time")
        if start and start > now_ms:
            states.append("upcoming")
        elif end and end < now_ms:
            states.append("ended")
        else:
            states.append("now")
    if "now" in states:
        return "now"
    if "upcoming" in states:
        return "upcoming"
    return "ended"


def overlaps(points: list[float], min_mp: float, max_mp: float) -> bool:
    if not points:
        return False
    lo, hi = min(points), max(points)
    return lo <= max_mp and hi >= min_mp


def summarize(feature: dict, now_ms: int) -> dict:
    props = feature.get("properties") or {}
    er = props.get("eventReport") or {}
    desc = er.get("eventDescription") or {}
    points = milepoints(feature)
    windows = []
    for window in er.get("scheduleOccurrences") or []:
        windows.append(
            {
                "start": ms_to_local((window.get("startTime") or {}).get("time")),
                "end": ms_to_local((window.get("endTime") or {}).get("time")),
            }
        )
    event_id = props.get("id")
    return {
        "id": event_id,
        "layer_type": props.get("eventType"),
        "when": timing(feature, now_ms),
        "direction": direction(feature),
        "milepoints": [round(p, 2) for p in points],
        "headline": strip_html(props.get("title") or desc.get("descriptionHeader") or ""),
        "detail": strip_html(desc.get("descriptionFull") or props.get("description") or ""),
        "updated": ms_to_local(props.get("updated")),
        "schedule": windows,
        "source": "Waze via COtrip" if str(event_id).startswith("Waze") else "CDOT",
        "map": f"https://www.cotrip.org/events/{event_id}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Query COtrip for a Colorado corridor")
    parser.add_argument("--corridor", default="i70-golden-denver", choices=sorted(CORRIDORS))
    parser.add_argument("--route", help="Override route designator, e.g. I-70, I-25, US 6")
    parser.add_argument("--min-mp", type=float)
    parser.add_argument("--max-mp", type=float)
    parser.add_argument(
        "--layers",
        default="incidents,closures,work,waze",
        help="Comma list: incidents,closures,work,waze,winter,chains",
    )
    parser.add_argument("--include-ended", action="store_true")
    args = parser.parse_args()

    spec = dict(CORRIDORS[args.corridor])
    if args.route:
        spec["route"] = args.route
    if args.min_mp is not None:
        spec["min_mp"] = args.min_mp
    if args.max_mp is not None:
        spec["max_mp"] = args.max_mp

    now = datetime.now(DENVER)
    now_ms = int(now.timestamp() * 1000)
    layers = [name.strip() for name in args.layers.split(",") if name.strip()]
    unknown = [name for name in layers if name not in LAYERS]
    if unknown:
        raise SystemExit(f"unknown layers: {unknown}")

    grouped = {name: [] for name in layers}
    for name in layers:
        url = f"{BASE}/events/map-features?eventClassifications={LAYERS[name]}"
        data = fetch(url)
        for feature in data.get("features") or []:
            props = feature.get("properties") or {}
            if props.get("route") != spec["route"]:
                continue
            points = milepoints(feature)
            if not overlaps(points, spec["min_mp"], spec["max_mp"]):
                continue
            item = summarize(feature, now_ms)
            if item["when"] == "ended" and not args.include_ended:
                continue
            grouped[name].append(item)

    order = {"now": 0, "upcoming": 1, "ended": 2}
    for items in grouped.values():
        items.sort(key=lambda item: (order.get(item["when"], 9), item.get("milepoints") or [0]))

    payload = {
        "queried_at": now.strftime("%Y-%m-%d %H:%M %Z"),
        "corridor": spec,
        "note": "CDOT active flag is true for future scheduled work. Use 'when', not active.",
        "counts": {name: len(items) for name, items in grouped.items()},
        "layers": grouped,
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
