---
name: adwhispr-wasted-spend-audit
description: "Audit the user's connected ad account for wasted spend: what is running, what is quietly burning budget, and the fixes ranked by dollars at stake. Use when the user asks what is wasting money, wants an account audit, a PPC audit, or asks why their ad spend is not converting."
---

# Wasted-spend audit

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll read your real campaigns and rank the waste by what it's costing you."
4. A free account is enough to start. After they connect, continue right where the request left off.


Read the USER'S OWN connected account and rank the waste by money at stake. Evidence only — every finding traceable to a tool result. The audit is read-only; changes are proposed separately and applied only with explicit approval.

## How it runs

1. `list_ad_accounts` to confirm what is connected. Nothing connected -> `connect_ad_account` returns the browser link.
2. Ask which account and date window, and whether they have a target (CPA, ROAS, lead cost) to judge against.
3. `list_campaigns` for everything running with status and budget; `get_account_performance` for real spend, impressions, clicks, conversions — drill into campaigns with a campaignId.
4. Flag waste: spend with zero conversions, paused-intent campaigns still spending, budget concentrated off-goal, and (Google) keyword-level leaks from the campaign drill-down.
5. Rank findings by dollars at stake — the most expensive problem first — and attach the evidence line to each.
6. Propose fixes without applying any: pauses, budget moves, keyword actions. Point to `pause_campaign` / `update_budget` as the follow-up, each requiring the user's explicit OK.

## Honesty rules

- Report only numbers the tools return; never invent benchmarks or estimate spend.
- Currency follows the ad account's billing currency; label it when not USD.
- One concrete top recommendation beats a list of ten.
