---
name: seo-bing
description: Bing Webmaster Tools + IndexNow extension. Microsoft Copilot citations are fed by the Bing index; this skill makes Bing visibility, link data, and IndexNow URL submission first-class.
metadata:
  version: "2.4.2"
compatibility: "Requires BING_WEBMASTER_API_KEY and optionally INDEXNOW_KEY as Duckwork profile-scoped secrets."
---

# seo-bing

The non-Google indexing surface. Google still rejects IndexNow (per
Gary Illyes, multiple SOTR episodes 2024-2025), so this skill is
specifically for **Amazon/Bing/Naver/Seznam.cz/Yandex/Yep indexing** and
**Microsoft Copilot AI citation** (which pulls from the Bing index).

## Prerequisites

- A Bing Webmaster Tools API key.
- Optional: an IndexNow host key (32+ chars) stored as the active profile's
  `INDEXNOW_KEY` secret and published at the nonsecret URL declared as
  `INDEXNOW_KEY_LOCATION`. Never pass the key in command arguments.

## Routing

| Command | Underlying script |
|---|---|
| Use the registered `duckwork-seo:seo-backlinks` workflow with Bing Webmaster/IndexNow links <url>` | `duckwork_seo_run {"script":"bing_webmaster.py","args":["links","<url>"]}` |
| Use the registered `duckwork-seo:seo-backlinks` workflow with Bing Webmaster/IndexNow compare <urlA> <urlB>` | `duckwork_seo_run {"script":"bing_webmaster.py","args":["compare","<urlA>","<urlB>"]}`; both properties must be registered to the API account |
| Submit one URL after explicit approval | `duckwork_seo_run {"script":"indexnow_submit.py","args":["--host","example.com","--key-location","https://example.com/indexnow-key.txt","--urls","https://example.com/new-page","--json"]}` |
| Submit a reviewed batch after explicit approval | `duckwork_seo_run {"script":"indexnow_submit.py","args":["--host","example.com","--key-location","https://example.com/indexnow-key.txt","--urls-file","urls.txt","--json"]}` |
| Verify the published key without submitting | `duckwork_seo_run {"script":"indexnow_submit.py","args":["--host","example.com","--key-location","https://example.com/indexnow-key.txt","--verify-only","--json"]}` |

## When this skill applies

- The user is publishing new pages and wants Microsoft Copilot
  citation eligibility (Bing index ingestion).
- The user wants to nudge Amazon/Bing/Naver/Seznam.cz/Yandex/Yep indexing for fresh
  URLs.
- The user manages both properties and wants to compare their Bing link data.
  For an arbitrary competitor, route to DataForSEO, Moz, or Common Crawl.

## Cross-skill delegation

- For Google indexing (very different model, sitemap-driven, no
  IndexNow), use `seo-google indexing`.
- For multi-source backlink confidence weighting, fall back to
  `seo-backlinks` which already integrates Bing + Moz + CC.
