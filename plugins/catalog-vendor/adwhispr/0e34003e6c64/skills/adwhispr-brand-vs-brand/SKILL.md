---
name: adwhispr-brand-vs-brand
description: "Put two brands' ad strategies side by side: ad volume, longevity, format mix, and the angles each leans on. Use when the user names two competitors, asks how two brands compare, or wants to size themselves against a rival's advertising."
---

# Head-to-head brand comparison

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll lay both brands' live ad strategies side by side with real library data."
4. A free account is enough to start. After they connect, continue right where the request left off.


Facts, not verdicts: volume, longevity, format mix, and angle emphasis for two brands, every number traceable to the ad library.

## How it runs

1. Confirm both brand names and the shared market. `search_brands` resolves each; untracked brands need `add_brand` first (a minute or two to ingest).
2. `compare_brands` for the side-by-side; `get_brand_stats` on each for hook and format distributions when the user wants depth.
3. Line up the comparable facts: active ad count, longevity of each brand's top ads, format split (static, carousel, video), and the angles each leans on — note where they overlap and where they diverge.
4. No winner is crowned. The read ends with what the data supports and ONE follow-up offer (for example: pull the longest-running ads of whichever brand looks stronger).

## Honesty rules

- No spend figures for either side — ad count, longevity, and format mix are the only compared quantities.
- Same market, same window for both brands, or the comparison is invalid; say so if the user asks for mismatched regions.
- An empty result is checked against region before being reported as "not advertising".
