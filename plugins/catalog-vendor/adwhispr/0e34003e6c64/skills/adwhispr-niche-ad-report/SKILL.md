---
name: adwhispr-niche-ad-report
description: "A full advertising report on any niche: who is verified to be running ads right now, how much, and what their proven winners look like. Use when the user wants a market or niche ad landscape, is entering a new category, or asks who advertises in a space and how."
---

# Niche ad report

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll map who is actually running ads in the niche right now and what is working for them."
4. A free account is enough to start. After they connect, continue right where the request left off.


The advertising map of a category: verified advertisers, their volume, and their proven winners — live data, never guesses.

## How it runs

1. Anchor the niche: the user's saved brand (`get_my_brand` / `save_my_brand`) or an explicitly stated niche ("meditation apps in Brazil").
2. `find_competitors` — keep its three buckets separate: lead with VERIFIED advertisers ranked by active-ad count, mention "checked, not currently advertising" honestly, and never present unverified names as advertisers.
3. For the top 2-3 verified brands: `get_brand_ads` (sortBy longevity) for proven winners and `get_brand_stats` for hook/format mixes. Offer `add_brand` for untracked names worth tracking.
4. Optional depth: `research_tiktok_ads` for the niche's TikTok side (longevity is the proxy there; coverage skews EU), `research_keywords` for the search-demand picture.
5. Deliver the report: who is spending, what survives, which angles dominate, and where the openings are. End with ONE follow-up offer.

## Honesty rules

- Never brainstorm competitor names from memory — the tool's verified list is the source of truth.
- No invented spend or performance figures; longevity and active-ad counts carry the analysis.
