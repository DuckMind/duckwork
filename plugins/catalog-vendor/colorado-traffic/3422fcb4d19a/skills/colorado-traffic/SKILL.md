---
name: colorado-traffic
description: "Use when asking about Colorado or I-70 traffic."
version: 1.1.0
author: Steven Hubert (drkpxl)
license: MIT
platforms: [macos, linux]
---

# Colorado traffic (COtrip)

Live Colorado road events come from CDOT's public COtrip 511 API. No key. Do not scrape Google Maps or Waze.

## When to Use

- Colorado traffic, I-70, COtrip, CDOT road conditions, a Golden to Denver commute, metro Denver highway incidents
- Don't use for mountain-weekend narrative forecasts (goi70.com) unless the user also wants live incidents west of Golden
- Don't use for historical volumes or planning studies (CDOT ArcGIS open data, not this API)

## Prerequisites

- Python 3.10 or newer (`int | None`, `zoneinfo`). If system Python is older, run the script with the agent venv interpreter.
- Network access to `https://api-511x-co.carsprogram.org`. No API key. No account.
- Optional travel time needs a Google Maps key already in the environment. The script never reads it. If the key is missing, say travel time is unavailable.

## How to Run

Run the script via `terminal`. Done when stdout is JSON with `queried_at`, `counts`, and `layers`.

```bash
python3 "${DUCKWORK_SKILL_DIR}/scripts/cotrip_corridor.py"
```

Other corridors: `--corridor i70-golden-i25`, or `--route "I-25" --min-mp 210 --max-mp 216`. Layers: `incidents,closures,work,waze,winter,chains`.

## Quick Reference

Default corridor is I-70 mile points **259-279**: C-470 / US-6 at Golden through Quebec Street in east Denver. Tighter Golden-to-I-25 box is **259-274.5**. A segment that only overlaps the west edge (Chief Hosa, MP 253-262) is mostly west of Golden. Say so.

Floyd Hill and the Eisenhower Tunnel are west of this box. Do not mix them into a Golden to Denver answer unless asked.

| Need | GET |
| --- | --- |
| Incidents | `/events/map-features?eventClassifications=roadReports` |
| Closures | `...roadClosures` |
| Construction | `...roadWork` |
| Waze reports CDOT already ingests | `...wazeReports` |
| Winter / chain law | `...winterDriving` / `...chainLaws` |
| Cameras | `/cameras/map-features` |
| DMS signs | `/signs/map-features` |

Base `https://api-511x-co.carsprogram.org`. Route list: `https://511.cotrip.org/configs/main.json`. Header `content-language: en`. No auth.

Bare `/events` returns `{"healthy":true}`. That is not an empty road. The data path is `/map-features`.

Filter on `properties.route` (string, e.g. `"I-70"`) and `eventReport.location.primaryPoint.linearReference` (mile point). Direction is `linkDirection` plus `routePositiveBearing`. On I-70, positive is eastbound. On I-25, positive is northbound. `BOTH_DIRECTIONS` means both, not the positive bearing.

Answer from the JSON in three buckets:

1. **Now** — `when == "now"`. Lead with these.
2. **Upcoming** — scheduled work. Give the Denver start and end, not just the headline.
3. **Waze** — crowd reports. Say "Waze via COtrip", not "CDOT confirmed".

`active: true` on a work event does **not** mean it is happening now. Future night closures are flagged active. Trust `when`.

Strip is already done. Do not paste raw HTML. Link `map` when the user wants the COtrip page.

Cameras: `views[].videoPreviewUrl` is a snapshot PNG; `views[].url` is HLS. Signs: `pages[].lines` is often a GIF URL, not readable text. Don't invent the message.

App poll intervals (from the config, not a webhook): events 60s, signs 30s, cameras 6 min. There is no public push. My511 alerts need a logged-in account. Don't promise push from this API.

Source notes and pricing live in `references/sources.md`.

## Procedure

### 1. Query the corridor the user asked for

Default is I-70 MP 259-279. Run the script via `terminal`. Done when exit code is 0 and stdout JSON has `queried_at` in America/Denver, `counts`, and `layers`.

### 2. Answer in three buckets

Lead with `when == "now"`. Then upcoming work, with Denver start and end. Then Waze, labeled "Waze via COtrip". Do not merge layers into one list. Cite only mile points inside the asked corridor. Done when each cited event names its bucket, direction, and mile points.

### 3. Travel time only if asked, and only with a key already present

COtrip does not publish speeds. The legal add-on is one Google Routes `computeRoutes` call with `routingPreference` `TRAFFIC_AWARE`. Report `duration` against `staticDuration`. Do not print the key. Do not scrape maps.google.com. If the key is missing, say travel time is unavailable. Do not guess minutes from Waze adjectives.

Example endpoints, not a command: Golden interchange `39.7555, -105.2211` to I-70/I-25 `39.7816, -104.9915`. Field mask `routes.duration,routes.staticDuration,routes.distanceMeters`. `departureTime`, if set, must be now or a future RFC3339 timestamp. Omitting it still returns a traffic-aware duration when `routingPreference` is `TRAFFIC_AWARE`.

Pricing (checked 2026-10-05): Compute Routes Pro, 5,000 free requests a month, then $10 / 1,000. One corridor query is one request.

### 4. A watcher only if the user asks

The skill is the on-demand path. Do not create a cron from a one-off question.

If they ask for alerts: a `no_agent` script, not an LLM every poll. Poll every 5 minutes. Persist `{id, updated, when}` for this corridor. Notify only on a new `now` closure, incident, or Waze standstill or jam, on the user's existing notify channel. Ignore the statewide `/events/hash`. It changes for Grand Junction. Done when the job exists and the first run did not notify on the baseline set.

## Pitfalls

1. Treating `{"healthy":true}` as "no incidents".
2. Treating `active: true` as "happening now".
3. Calling a Waze report a CDOT incident.
4. Answering Golden to Denver with Floyd Hill or tunnel metering.
5. Scraping Google or Waze because the official JSON is right there.
6. Quoting a DMS GIF URL as if it were the sign text.
7. Calling every `POSITIVE_DIRECTION` eastbound. On I-25 it is northbound. Use `routePositiveBearing`.
8. Putting an API key in a command in this skill. The script does not read one. A missing key means no travel-time number.

## Verification

- [ ] Script exit 0 and JSON has `queried_at` in America/Denver
- [ ] Incidents, work, and Waze are not merged into one list
- [ ] Mile points cited are inside the corridor the user asked for
- [ ] Direction follows `routePositiveBearing`, not a hardcoded east/west
- [ ] No travel-time number unless a Routes API call returned one
