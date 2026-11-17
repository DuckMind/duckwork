---
name: seo-matomo
description: Matomo Reporting API extension. Self-hosted or Matomo Cloud analytics as a GA4 alternative or complement. Organic traffic, landing pages, device / country breakdowns, referrers, search keywords. Triggers on "Matomo", "self-hosted analytics", "analytics ohne Google", "GA4 alternative", "Matomo Reporting", "Piwik".
metadata:
  version: "2.4.2"
compatibility: "Requires MATOMO_URL, MATOMO_API_TOKEN or MATOMO_TOKEN, and optionally MATOMO_SITE_ID or MATOMO_IDSITE in the active Duckwork profile vault."
---

# seo-matomo

Self-hosted analytics surface. Use Matomo as a privacy-first GA4 alternative
when you own your analytics data, want zero Google dependency, or operate
behind a strict data-residency boundary. The same `seo-matomo` skill works
against Matomo Cloud and self-hosted instances.

## Prerequisites

- A Matomo instance URL (https://analytics.example.com).
- A Matomo API `token_auth` with `view` access on the sites you analyze.
- (Optional) A default `idSite` to avoid passing `--site-id` on every call.
- Store all supported values in the active Duckwork profile vault. The native
  tool resolves them with `agent.secret_scope.get_secret()`.

## Routing

This extension file is an optional companion reference, not a separately
registered Duckwork skill. For bundled API access, ask for approval for the
external request and call `duckwork_seo_run` with arguments such as
`{"script":"matomo_auth.py","args":["--check","--json"]}` or
`{"script":"matomo_report.py","args":["organic","--json"]}`. There is no
CLI or plugin-file credential setup path.

All reports accept `--days` (default 28), `--limit`, `--site-id`, and
`--json`. Without `--site-id`, the tool injects `MATOMO_SITE_ID` or
`MATOMO_IDSITE` from the active profile vault.

## When this skill applies

- The user wants Google-free analytics or has a Matomo instance already
  configured. Common in EU privacy-first setups, regulated industries,
  and teams who own their analytics.
- The user explicitly says "Matomo", "self-hosted analytics", or asks to
  replace GA4. For Google Search performance use `seo-google`; this
  skill is the reporting substitute.
- The user is migrating from GA4 and wants the same report types
  (organic trend, landing pages, device / country split, referrer split)
  sourced from Matomo's Reporting API.

## Cross-skill delegation

- For Google Search Console / CrUX / Indexing, route to `seo-google`.
  `seo-matomo` covers reporting (visits / pages / referrers), not search
  performance metrics.
- For AI Overview / GEO citability work, route to `seo-geo`. Matomo
  offers no LLM-specific signals.
- During `duckwork-seo:seo-audit`, use Matomo inline when
  `duckwork_seo_run` with
  `{"script":"matomo_auth.py","args":["--check","--json"]}` succeeds.

## Self-hosted instance on a private address

Every Matomo request goes through Duckwork SEO SSRF guard: the instance URL
is validated and DNS-pinned, and a redirect off the instance is refused.
Private, loopback, and link-local addresses are refused by default. For a
trusted private Matomo instance, store the exact host or host and port in
`DUCKWORK_SEO_LOCAL_TARGETS` in the active Duckwork profile vault. The native tool
injects it only for Matomo scripts. Never suggest disabling the guard or
editing `url_safety.py`.

## Error Handling

- Refused by the SSRF guard: report that the exact Matomo host must be added to
  the active profile's `DUCKWORK_SEO_LOCAL_TARGETS` value.
- Refused redirect: the instance answered a 30x pointing at another host.
  `MATOMO_URL` is pointing at a redirector rather than at the Reporting API.
  Ask the user for the URL their instance actually serves the API from.
- Missing configuration: report which supported vault names are unset. Never
  request values in tool arguments or write a plugin configuration file.
- HTTP 401/403 from Matomo: the token lacks view access for the given
  site. Verify the token scope in Matomo Administration -> Personal ->
  Security -> API Tokens. The skill never logs the token.
- `result=error` payloads from Matomo (e.g. invalid `idSite`): surface
  the message verbatim; do not guess.
- Connection / SSL / timeout: report the network failure class
  (`ConnectionError`, `SSLError`, `timeout`) and confirm
  `MATOMO_URL` resolves.

## Output Formatting

- Tables for time-series, device, and country data.
- Critical / High / Medium / Low priority for any cross-skill actions
  surfaced from Matomo data.
- Always label the data source as "Matomo Reporting API (live)" to
  distinguish from GA4, CrUX, or static crawl analysis.
- For organic keywords, surface the `anonymized_share_pct` prominently.
  Many keywords will be "(not provided)" due to browser privacy and
  Matomo's anonymization rules; this is normal, not a data bug.
