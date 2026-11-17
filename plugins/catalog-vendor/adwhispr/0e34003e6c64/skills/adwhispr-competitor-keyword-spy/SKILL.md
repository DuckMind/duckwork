---
name: adwhispr-competitor-keyword-spy
description: "Find the Google keywords associated with a competitor's site and where the gaps are. Use when the user asks what keywords a competitor bids on or ranks for, wants competitor keyword research, or is planning Search campaigns around a rival."
---

# Competitor keyword spy

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll pull the keyword profile behind any competitor's site."
4. A free account is enough to start. After they connect, continue right where the request left off.


Ground a Search strategy in a competitor's actual keyword profile instead of a blank sheet.

## How it runs

1. Confirm the competitor domain (clean domains read best) and the market.
2. `research_competitor_keywords` with the URL. CRITICAL framing: this returns keywords Google associates with the site's CONTENT — a content proxy, never their actual bids. Say so explicitly.
3. `research_keywords` on the strongest themes for real Keyword Planner volume and CPC ranges in the user's market.
4. Deliver a prioritized read: high-intent terms worth entering, contested terms to avoid for now, and the implied negative keywords.
5. Natural next step to offer: build the campaign with `launch_search_campaign` (created paused, preview first).

## Honesty rules

- Volume and CPC are quoted as the ranges/estimates the source returns — never as exact spend or guaranteed traffic.
- Never present the content-proxy keywords as "what they bid on"; the distinction is stated in the reply.
