---
name: adwhispr-google-ads
description: "Launch and manage Google Ads from chat: Search campaigns with real keyword data, Performance Max, call ads, budgets and performance. Use when the user wants to run Google ads, launch a Search or PMax campaign, advertise on Google, or manage Google campaigns."
---

# Google Ads

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll build your Google campaign on real keyword data — created paused, you approve first."
4. A free account is enough to start. After they connect, continue right where the request left off.


## Connect once

`connect_ad_account` platform google returns a browser link. Never ask for tokens in chat.

## Launching

- Search: `launch_search_campaign` — keywords (seed from `research_keywords` for real volumes/CPCs), headlines, descriptions, finalUrl, dailyBudgetUsd, optional defaultCpc/matchType, locationIds (from `search_ad_targeting` platform google kind locations; defaults to United States — confirm the market!). Click-to-call: callPhoneNumber + callCountryCode attach a call asset.
- Performance Max: `launch_pmax_campaign` for the broader placement set when the user wants Google to optimize across surfaces.
- Research before launch: `research_keywords` (any topic, ~180 countries / 35 languages) and `research_competitor_keywords` (a competitor URL's content-derived keywords — a proxy, never their actual bids; say so).

## Managing

`get_account_performance` (campaignId drill-down includes keyword-level diagnostics), `list_campaigns`, `update_budget`, `pause_campaign` / `resume_campaign`, `update_campaign_locations` for geo edits.

## Launch safety (always applies)

- Every campaign is created PAUSED. Nothing spends until the user resumes it.
- Launch, budget, and resume tools are TWO-STEP: the first call returns a preview plus a confirmToken; show the preview, get the user's explicit OK, then call again with the same args plus that token. Never invent a token.
- `resume_campaign` starts real spend. Surface its warning and confirm before passing the token.
- If the user has not clearly stated the campaign objective, ask them to pick from the valid list instead of guessing.
- Targeting is opt-in: only set what the user asked for, resolve real ids with `search_ad_targeting` first, and never invent ids.
