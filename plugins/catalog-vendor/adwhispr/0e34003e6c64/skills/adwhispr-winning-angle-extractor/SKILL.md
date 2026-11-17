---
name: adwhispr-winning-angle-extractor
description: "Extract the angles and offers behind a brand's longest-running ads, categorized into reusable patterns. Use when the user wants ad angles, messaging analysis, hook ideas, what offers a competitor runs, or inspiration for writing their own ads."
---

# Winning angle and offer extractor

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll decode the messaging patterns behind your competitors' proven ads."
4. A free account is enough to start. After they connect, continue right where the request left off.


Read a brand's long-running ads and distill the messaging into named, reusable patterns — price framing, urgency, social proof, problem-solution, identity — never paste-ready copy of their words.

## How it runs

1. Confirm the brand and market; resolve with `search_brands`, ingest with `add_brand` if untracked.
2. `get_brand_ads` with `sortBy: longevity` — only ads with real staying power feed the angle set.
3. Read each survivor's core angle, offer, and framing. `search_ads` within the brand finds thematic clusters ("testimonial ads", "before/after"); `get_brand_stats` gives the hook and format distributions behind them.
4. Group into named patterns, note which offers recur (discount, bundle, guarantee, free trial) and which angles the brand leaves unused — gaps the user can take.
5. Deliver categorized patterns, each traceable to the ads it came from, framed as strategy inputs to adapt — never copy to reuse verbatim.

## Honesty rules

- Longevity selects the ads; no other performance figure is attached to any angle.
- Patterns, not quotes: the deliverable is abstracted, so the user ships their own voice.
- An "unused angle" is only unused in the confirmed market.
