---
name: adwhispr-keyword-universe-builder
description: "Build a complete keyword universe for any product or topic with real Google Keyword Planner data in ~180 countries and 35 languages. Use when the user wants keyword research, search volumes, CPC estimates, or a keyword list for a new campaign or market."
---

# Keyword universe builder

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll pull real Google Keyword Planner volumes for your topic in any market."
4. A free account is enough to start. After they connect, continue right where the request left off.


Real Keyword Planner data — average monthly searches and CPC ranges — for any topic, in nearly any country and language.

## How it runs

1. Confirm the topic or product and the market (country + language). Coverage is ~180 countries and 35 languages; non-US and non-English markets work.
2. `research_keywords` with seed terms. Run 2-3 seed variations to widen the universe (product terms, problem terms, brand-adjacent terms).
3. Group results by intent: buy-now, comparison, problem/informational. Flag the high-intent, affordable middle.
4. Optionally cross-reference a competitor with `research_competitor_keywords` to find terms the user is missing.
5. Offer the natural next step: a paused Google Search campaign from the top group via `launch_search_campaign`.

## Honesty rules

- Volumes and CPCs are Google's estimates and ranges; quote them that way.
- A thin result in a small market is reported as thin, not padded with invented terms.
