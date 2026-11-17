---
name: seo-drift
description: "Capture and compare SEO changes over time."
author: Daniel Agrici
license: MIT
---

# SEO Drift Monitor (April 2026)

Git for your SEO. Capture baselines, detect regressions, track changes over time.

---

## Commands

| Command | Purpose |
|---------|---------|
| `duckwork-seo:seo-drift baseline <url>` | Capture current SEO state as a "known good" snapshot |
| `duckwork-seo:seo-drift compare <url>` | Compare current page state to stored baseline |
| `duckwork-seo:seo-drift history <url>` | Show change history and past comparisons |

---

## What It Captures

Every baseline records these SEO-critical elements:

| Element | Field | Source |
|---------|-------|--------|
| Title tag | `title` | `parse_html.py` |
| Meta description | `meta_description` | `parse_html.py` |
| Canonical URL | `canonical` | `parse_html.py` |
| Robots directives | `meta_robots` | `parse_html.py` |
| H1 headings | `h1` (array) | `parse_html.py` |
| H2 headings | `h2` (array) | `parse_html.py` |
| H3 headings | `h3` (array) | `parse_html.py` |
| JSON-LD schema | `schema` (array) | `parse_html.py` |
| Open Graph tags | `open_graph` (dict) | `parse_html.py` |
| Core Web Vitals | `cwv` (dict) | `pagespeed_check.py` |
| HTTP status code | `status_code` | `fetch_page.py` |
| HTML content hash | `html_hash` (SHA-256) | Computed |
| Schema content hash | `schema_hash` (SHA-256) | Computed |

---

## How Comparison Works

The comparison engine applies **17 rules across 3 severity levels**. Load
`references/comparison-rules.md` for the full rule set with thresholds,
recommended actions, and cross-skill references.

### Severity Levels

| Level | Meaning | Response Time |
|-------|---------|---------------|
| **CRITICAL** | SEO-breaking change, likely traffic loss | Immediate |
| **WARNING** | Potential impact, needs investigation | Within 1 week |
| **INFO** | Awareness only, may be intentional | Review at convenience |

---

## Storage

All data is stored locally in SQLite:

```
~/.cache/Duckwork SEO/drift/baselines.db
```

### Tables

- **baselines**: Captured snapshots with all SEO elements
- **comparisons**: Diff results with triggered rules and severities

URL normalization ensures consistent matching: lowercase scheme/host, strip
default ports (80/443), sort query parameters, remove UTM parameters, strip
trailing slashes.

---

## Command: `baseline`

Captures the current state of a page and stores it.

**Steps:**
1. Validate URL (SSRF protection via `google_auth.validate_url()`)
2. Fetch page via `duckwork seo run fetch_page.py <URL>`
3. Parse HTML via `duckwork seo run parse_html.py <URL>`
4. Optionally fetch CWV via `duckwork_seo_run {"script":"pagespeed_check.py","args":["<URL>"]}` (use `--skip-cwv` to skip)
5. Hash HTML body and schema content (SHA-256)
6. Store snapshot in SQLite

**Execution:**
```bash
duckwork seo run drift_baseline.py <url>
duckwork seo run drift_baseline.py <url> --skip-cwv
```

**Output:** JSON with baseline ID, timestamp, URL, and summary of captured elements.

---

## Command: `compare`

Fetches the current page state and diffs it against the most recent baseline.

**Steps:**
1. Validate URL
2. Load most recent baseline from SQLite (or specific `--baseline-id`)
3. Fetch and parse current page state
4. Run all 17 comparison rules
5. Classify findings by severity
6. Store comparison result
7. Output JSON diff report

**Execution:**
```bash
duckwork seo run drift_compare.py <url>
duckwork seo run drift_compare.py <url> --baseline-id 5
duckwork seo run drift_compare.py <url> --skip-cwv
```

**Output:** JSON with all triggered rules, old/new values, severity, and actions.

After comparison, offer to generate an HTML report:
```bash
duckwork seo run drift_report.py <comparison_json_file> --output drift-report.html
```

---

## Command: `history`

Shows all baselines and comparisons for a URL.

**Execution:**
```bash
duckwork seo run drift_history.py <url>
duckwork seo run drift_history.py <url> --limit 10
```

**Output:** JSON array of baselines (newest first) with timestamps and comparison summaries.

---

## Cross-Skill Integration

When drift is detected, recommend the appropriate specialized skill:

| Finding | Recommendation |
|---------|----------------|
| Schema removed or modified | Run `duckwork-seo:seo-schema <url>` for full validation |
| CWV regression | Run `duckwork-seo:seo-technical <url>` for performance audit |
| Title or meta description changed | Run `duckwork-seo:seo-page <url>` for content analysis |
| Canonical changed or removed | Run `duckwork-seo:seo-technical <url>` for indexability check |
| Noindex added | Run `duckwork-seo:seo-technical <url>` for crawlability audit |
| H1/heading structure changed | Run `duckwork-seo:seo-content <url>` for E-E-A-T review |
| OG tags removed | Run `duckwork-seo:seo-page <url>` for social sharing analysis |
| Status code changed to error | Run `duckwork-seo:seo-technical <url>` for full diagnostics |

---

## Error Handling

| Scenario | Action |
|----------|--------|
| URL unreachable | Report error from `fetch_page.py`. Do not guess state. Suggest user verify URL. |
| No baseline exists for URL | Inform user and suggest running `baseline` first. |
| SSRF blocked (private IP) | Report `validate_url()` rejection. Never bypass. |
| SQLite database missing | Auto-create on first use. No error. |
| CWV fetch fails (no API key) | Store `null` for CWV fields. Skip CWV rules during comparison. |
| Page returns 4xx/5xx | Still capture as baseline (status code IS a tracked field). |
| Multiple baselines exist | Use most recent unless `--baseline-id` specified. |

---

## Security

- **All URL fetching** goes through `duckwork seo run fetch_page.py`, which enforces SSRF protection
  (blocks private IPs, loopback, reserved ranges, GCP metadata endpoints)
- **No curl, no subprocess HTTP calls** -- only the project's validated fetch pipeline
- **All SQLite queries** use parameterized placeholders (`?`), never string interpolation
- **TLS always verified** -- no `verify=False` anywhere in the pipeline

---

## Typical Workflows

### Pre/Post Deployment Check
```
`duckwork-seo:seo-drift` baseline https://example.com     # Before deploy
# ... deploy happens ...
`duckwork-seo:seo-drift` compare https://example.com      # After deploy
```

### Ongoing Monitoring
```
`duckwork-seo:seo-drift` baseline https://example.com     # Initial capture
# ... weeks later ...
`duckwork-seo:seo-drift` compare https://example.com      # Check for drift
`duckwork-seo:seo-drift` history https://example.com      # Review all changes
```

### Investigating a Traffic Drop
```
`duckwork-seo:seo-drift` compare https://example.com      # What changed?
`duckwork-seo:seo-drift` history https://example.com      # When did it change?
```
