---
name: hypd-workflows
description: Ready-made HYPD analyses for paid media, such as a Google Ads account audit, wasted spend, negative keywords, keyword research, a performance-drop diagnosis, a monthly client report, Merchant Center feed checks, Meta account diagnosis, creative and competitor analysis, and landing-page audits. Use when the user asks for one of these, or asks which analyses HYPD offers.
---

# HYPD workflows

HYPD keeps a library of saved analysis templates on its server. A template is a checklist of what to look at and which output sections to produce. Fetching one does not run anything or touch an ad platform.

## Steps

1. Pick the template key from the table below. If nothing fits, call `prompt_templates_list` (filter by `platform`, `category` or `query`) and **only use entries whose `runsIn` is `any`**.
2. Resolve the account the user means (`google_ads_list_accounts`, `meta_list_ad_accounts`, `microsoft_ads_list_accounts`, `linkedin_list_ad_accounts`, `merchant_center_list_accounts`, `google_analytics_list_account_summaries` or `search_console_list_sites`). Google Ads IDs are 10 digits with no dashes.
3. Call `prompt_templates_get` with the key. Use the returned text as the checklist for the analysis. It may list inputs it needs; the user's request often answers them already, so ask only for what is still missing.
4. Run the analysis with HYPD's tools and deliver the sections the template describes, most important findings first. These templates analyse and recommend; they make no changes.

## Common requests

| The user wants | Template key |
|---|---|
| Full Google Ads account audit | `standard-account-audit` |
| Quick health check / thorough audit | `fast-account-health-check` / `deep-account-audit` |
| Wasted spend, with the money behind each finding | `analyze-wasted-spend-efficiency` |
| Negative keyword candidates from search terms | `identify-negative-keywords` |
| Keywords for a new search campaign | `keyword-research-for-a-new-search-campaign` |
| More keywords for an existing campaign | `keyword-expansion-for-an-existing-search-campaigns` |
| Why performance dropped | `performance-drop-diagnosis` |
| Client-ready monthly report | `monthly-performance-report` |
| Compare two time periods | `compare-the-performance-of-two-time-periods` |
| Conversion tracking health | `conversion-tracking-health-check` |
| Merchant Center feed quality | `mc-feed-quality-audit` |
| Merchant Center disapprovals | `mc-disapproval-triage` |
| What is going wrong in a Meta account | `meta-root-cause-analysis` |
| Weekly Meta recap | `meta-weekly-paid-media-recap` |
| Creative analysis (own ads) | `creative-analysis` |
| Competitor ads and creative | `competitor-creative-analysis` |
| Top opportunities across Google and Meta | `top-10-opportunities` |
| Technical landing-page audit | `technical-landing-page-audit` |
| GA4 month-on-month | `ga4-month-on-month` |

Keyword research tools need a country and a language. If HYPD is not connected, follow the **hypd-getting-started** skill.
