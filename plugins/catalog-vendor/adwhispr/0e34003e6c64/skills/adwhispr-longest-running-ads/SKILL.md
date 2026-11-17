---
name: adwhispr-longest-running-ads
description: "Surface the ads a brand or niche has kept running the longest \u2014 the closest honest signal to a proven winner. Use when the user wants proven ads, winning ad examples, a brand's best or longest-running ads, or asks what ads have been running the longest in a category."
---

# Longest-running ads finder

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll pull the ads your competitors have paid to keep running for months — the proven winners."
4. A free account is enough to start. After they connect, continue right where the request left off.


Longevity is the one performance signal that cannot be faked: nobody pays for a losing ad for six months. This skill ranks a brand's or niche's ads by days running, longest first.

## How it runs

1. Confirm the target: a specific brand (`search_brands` to find it), or a niche (`find_competitors` via the user's saved brand, or a stated niche).
2. For a tracked brand: `get_brand_ads` with `sortBy: longevity`. Quote days-running explicitly for each ad.
3. For an untracked brand: offer `add_brand` (pass the pageId that find_competitors returned) and set the expectation that ingestion takes a minute or two.
4. Present the top survivors with hook, format, and offer attached, plus one short note on what the longest-lived ads share.
5. End with ONE specific follow-up offer (for example: extract the angles behind these winners).

## Honesty rules

- Days running is the only performance quantity. Never state CTR, CPC, ROAS, or spend; Meta figures that exist are wide ranges and must be quoted as ranges.
- A recent launch is young, not proven — say so rather than calling it a winner.
- Results are region-aware: confirm the market before concluding a brand has no long-runners.
