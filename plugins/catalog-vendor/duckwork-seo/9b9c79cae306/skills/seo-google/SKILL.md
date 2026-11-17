---
name: seo-google
description: "Analyze Google Search Console and performance data."
author: Daniel Agrici
license: MIT
---

OAuth services are disabled in the catalog build: GSC, GA4, Google Ads Keyword
Planner, and Indexing API. Do not invoke their legacy scripts. Duckwork 0.22.2
does not provide an approved Google OAuth route; only static API-key Google
services below are available.

# Google SEO APIs

Static-key access to selected Google SEO data. Google Search Console, GA4,
Google Ads Keyword Planner, and Indexing API remain unavailable in this catalog
build because Duckwork 0.22.2 has no approved profile-scoped Google OAuth route.

## Prerequisites

Store `GOOGLE_API_KEY` in the active Duckwork profile vault. Before using a
static-key service, ask the user to approve the external request, then call
`duckwork_seo_run` with:

```json
{"script":"google_auth.py","args":["--check","--json"]}
```

The tool resolves only the allowlisted `GOOGLE_API_KEY` from Duckwork
`agent.secret_scope`; never pass credentials in `args`, files, or shell commands.
See `references/auth-setup.md` for the supported boundary.

The following references describe Google OAuth or account-scoped APIs that are
disabled in this catalog release; they are retained for background only and do
not document runnable workflows: `references/ga4-data-api.md`,
`references/search-console-api.md`, `references/indexing-api.md`,
`references/keyword-planner-api.md`, and
`references/dma-consent-mode-v2.md`.

## Quick Reference

| Command | What it does | Tier |
|---------|-------------|------|
| Static-key check | `duckwork_seo_run {"script":"google_auth.py","args":["--check","--json"]}` | 0 |
| `duckwork-seo:seo-google pagespeed <url>` | PSI Lighthouse + CrUX field data | 0 |
| `duckwork-seo:seo-google crux <url>` | CrUX field data only (p75 metrics) | 0 |
| `duckwork-seo:seo-google crux-history <url>` | 25-week CWV trend analysis | 0 |
| GSC, GA4, Indexing API commands | Disabled: Duckwork has no approved Google OAuth route | n/a |
| `duckwork-seo:seo-google youtube <query>` | YouTube video search (views, likes, duration) | 0 |
| `duckwork-seo:seo-google youtube-video <id>` | YouTube video details + top comments | 0 |
| `duckwork-seo:seo-google nlp <url-or-text>` | NLP entity extraction + sentiment + classification | 0 |
| `duckwork-seo:seo-google entities <url-or-text>` | Entity analysis only (for E-E-A-T) | 0 |
| Google Ads Keyword Planner | Disabled: requires Google OAuth | n/a |
| `duckwork-seo:seo-google entity <query>` | Knowledge Graph entity check | 0 |
| `duckwork-seo:seo-google safety <url>` | Web Risk URL safety check | 0 |
| `duckwork-seo:seo-google quotas` | Show rate limits for all APIs | -- |

---

## PageSpeed + CrUX

### `duckwork-seo:seo-google pagespeed <url>`

Combined Lighthouse lab data + CrUX field data.

**Script:** `duckwork_seo_run {"script":"pagespeed_check.py","args":["<url>","--json"]}`
**Reference:** `references/pagespeed-crux-api.md` (Core Web Vitals thresholds: `references/crux-history-api.md`)
**Report the Lighthouse build** from the output's `lighthouse_version` field instead of assuming the latest release.
**Default:** Both mobile + desktop strategies, all Lighthouse categories.

Output merges lab scores (point-in-time Lighthouse) with field data (28-day
Chrome user metrics). CrUX tries URL-level first, falls back to origin-level.

### `duckwork-seo:seo-google crux <url>`

CrUX field data only (no Lighthouse run). Faster.

**Script:** `duckwork_seo_run {"script":"pagespeed_check.py","args":["<url>","--crux-only","--json"]}`

### `duckwork-seo:seo-google crux-history <url>`

25-week CrUX History trends. Shows whether CWV metrics are improving, stable, or degrading.

**Script:** `duckwork_seo_run {"script":"crux_history.py","args":["<url>","--json"]}`
**Reference:** `references/crux-history-api.md`

Output includes per-metric trend direction, percentage change, and weekly p75 values.

---

## OAuth-backed Google services

Google Search Console, GA4, Google Ads Keyword Planner, and Indexing API are
disabled in this catalog build. Do not run the retained GSC, GA4, Ads, or
Indexing scripts and do not configure service-account files, ADC, refresh
tokens, or browser OAuth. Their reference material describes upstream API
semantics only and is not an executable setup path for this port.

Sitemap submission or sitemap reports do not confirm that a URL is indexed.
Historically, URL Inspection is the reference for per-URL indexation status,
but it is unavailable in this catalog build.

---

## YouTube (Video SEO)

Some third-party studies report a 0.737 correlation between YouTube mentions and AI visibility. Treat it as a methodology-dependent signal. Free, API key only.

### `duckwork-seo:seo-google youtube <query>`

Search YouTube for videos. Returns title, channel, views, likes, duration.

**Script:** `duckwork_seo_run {"script":"youtube_search.py","args":["search","<query>","--json"]}`
**Reference:** `references/youtube-api.md`
**Quota:** 100 units per search (10,000 units/day free).

### `duckwork-seo:seo-google youtube-video <video_id>`

Detailed video info + tags + top 10 comments.

**Script:** `duckwork_seo_run {"script":"youtube_search.py","args":["video","<video_id>","--json"]}`
**Quota:** 2 units (video details + comments).

---

## NLP Content Analysis

Google NLP entity/sentiment output for internal content-quality checks. Do not treat it as Google E-E-A-T scoring.

### `duckwork-seo:seo-google nlp <url-or-text>`

Full NLP analysis: entities, sentiment, content classification.

**Script:** `duckwork_seo_run {"script":"nlp_analyze.py","args":["--url","<url>","--json"]}` or `duckwork_seo_run {"script":"nlp_analyze.py","args":["--text","..."]}`
**Reference:** `references/nlp-api.md`
**Free tier:** 5,000 units/month. Requires billing enabled on GCP project.

### `duckwork-seo:seo-google entities <url-or-text>`

Entity extraction only (faster, less quota).

**Script:** `duckwork_seo_run {"script":"nlp_analyze.py","args":["--url","<url>","--features","entities","--json"]}`

---

## Supplementary

### `duckwork-seo:seo-google entity <query>`

Knowledge Graph entity check. Verifies brand presence.

**Reference:** `references/supplementary-apis.md`
Uses Knowledge Graph Search API with API key.

### `duckwork-seo:seo-google safety <url>`

Web Risk API check for malware/social engineering flags.

**Reference:** `references/supplementary-apis.md`

### `duckwork-seo:seo-google quotas`

Display rate limits table. Load with `skill_view(name="duckwork-seo:seo-google", file_path="references/rate-limits-quotas.md")`.

---

## Reports

After any analysis command, offer to generate a PDF/HTML report.

### `duckwork-seo:seo-google report <type>`

Generate a professional PDF report with charts and analytics.

**Script:** `duckwork seo run google_report.py --type <type> --data <json> --domain <domain> --format pdf`

| Type | Input | Output |
|------|-------|--------|
| `cwv-audit` | PSI + CrUX + CrUX History data | Core Web Vitals audit with gauges, timelines, distributions |

**Workflow:**
1. Run PageSpeed and CrUX collection through `duckwork_seo_run` after approval.
2. Save the returned JSON as `data.json` with an approved file-write tool.
3. Generate report: `duckwork seo run google_report.py --type cwv-audit --data data.json --domain <domain>`

**Convention:** After completing analysis, suggest: "Generate a report? Use `duckwork-seo:seo-google report <type>`"

---

## Rate Limits

| API | Per-Minute | Per-Day | Auth |
|-----|-----------|---------|------|
| PSI v5 | 240 QPM | 25,000 QPD | API Key |
| CrUX + History | 150 QPM (shared) | Unlimited | API Key |

## Cross-Skill Integration

- **seo-audit**: Uses the Google role only for approved static-key services such as PageSpeed and CrUX
- **seo-technical**: Uses pagespeed_check.py for real CWV field data
- **seo-performance**: CrUX field data supplements Lighthouse lab data

## Output Format

- CWV metrics: traffic-light rating (Good / Needs Improvement / Poor)
- Performance reports: tables with sortable columns
- Always include data freshness note
- Save reports as `GOOGLE-API-REPORT-{domain}.md`
- Markdown/LLM templates in `assets/templates/`: `cwv-audit-report.md`, `gsc-performance-report.md`, `indexation-status-report.md`; distinct from `google_report.py`'s PDF pipeline

## Technical Notes

- INP replaced FID on March 12, 2024. Never reference FID.
- CLS values from CrUX are string-encoded (e.g., "0.05"). Scripts handle parsing.
- CrUX 404 = insufficient traffic, not an auth error.
- Search Analytics data has 2-3 day lag.
- `round_trip_time` replaced `effectiveConnectionType` in CrUX (Feb 2025).
- Custom Search JSON API is closed to new customers (2025).

## Error Handling

| Scenario | Action |
|----------|--------|
| No static API key configured | Ask the user to add `GOOGLE_API_KEY` to the active Duckwork profile vault. |
| CrUX data unavailable (404) | Report insufficient Chrome traffic. Suggest PSI lab data as fallback. |
| Rate limit (429) | Wait and retry with exponential backoff. Report which API hit the limit. |
