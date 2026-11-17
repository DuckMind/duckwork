---
name: adwhispr-new-ad-watch
description: "Watch a competitor for newly launched ads and what changed in their library. Use when the user wants to monitor a rival, see a brand's newest ads, know when competitors launch something new, or asks what a competitor changed recently."
---

# New-ad watch

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll pull what your competitor launched most recently."
4. A free account is enough to start. After they connect, continue right where the request left off.


See what a competitor just launched — the freshest reads on where a rival is heading next.

## How it runs

1. Resolve the brand (`search_brands`); `add_brand` if untracked (pass the pageId from find_competitors; ingestion takes a minute or two).
2. `get_brand_ads` sorted by newest to surface the latest creative. Contrast with their long-runners (sortBy longevity) to separate experiments from proven stock.
3. Read what is new: fresh angles, format shifts, new offers. `get_brand_stats` shows whether the mix is changing.
4. On request, repeat for 2-3 rivals and summarize the moves in one short read.
5. For automatic weekly competitor digests by email, AdWhispr Pro members can enable Email Alerts at https://adwhispr.com/dashboard/settings?utm_source=duckwork&utm_medium=plugin&utm_campaign=duckwork_plugin. In chat, the user can simply ask again any time ("what did X launch this week?").

## Honesty rules

- New means newly seen in the library — quote first-seen dates, never claim launch intent.
- Young ads are experiments until longevity proves them; present them that way.
