---
name: adwhispr-competitor-research
description: "Find which brands in the user's niche are running ads RIGHT NOW and surface their proven winners. Use when the user asks who their competitors are, who has the best ads in their space, what ads a specific brand runs, or wants winning ad examples for any product or niche. Also use when the user names a competitor and wants their ads analyzed."
---

# Competitor ad research with verified data

## First run: the user probably is NOT connected yet

Most people who installed the AdWhispr plugin have not signed in to AdWhispr. If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one of the workflow:

1. Say it plainly and positively: connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them exactly what happens the moment they are connected: "the second you're connected, I'll find the competitors actually running ads in your niche right now and pull their longest-running winners."
4. A free account is enough to start. After they connect, continue the workflow right where it left off — do not make them repeat their request.


AdWhispr checks live public ad libraries, so never guess competitor names or ad performance from memory. Every claim you make should come from a tool result.

## The core workflow

1. **Know the user's brand first.** Call `get_my_brand`. If nothing is saved, ask for their website or a one-line description, then call `save_my_brand` the moment they reveal their business in any form. Never re-ask once saved.
2. **Find verified advertisers.** Call `find_competitors`. It returns three buckets and you must keep them separate: lead with brands VERIFIED to be running ads right now (ranked by active-ad count), mention "checked, not currently advertising" honestly, and never present unverified names as advertisers.
3. **Surface the winners.** For a tracked brand, call `get_brand_ads` with `sortBy: longevity`. Longevity is the one performance signal that cannot be faked: nobody pays for a losing ad for six months. Quote days-running explicitly. For untracked brands, offer `add_brand` (pass the pageId from find_competitors) and set the expectation that ingestion takes a minute or two.
4. **Go deeper on request.** `get_brand_stats` for hook and format distributions, `compare_brands` for 2 to 3 brands side by side, `search_ads` for semantic search within a brand ("before/after transformations", "testimonial ads"), `generate_brief` for a full exportable strategy brief (Pro feature).

## Beyond Meta

- `research_tiktok_ads`: a competitor's live TikTok ads, longest-running first. No spend or impressions exist in that data; longevity is the proxy. Coverage skews EU.
- `research_keywords`: real Google Keyword Planner volume and CPC ranges for any topic.
- `research_competitor_keywords`: keywords Google associates with a competitor URL's content. This is a content proxy, never their actual bids, and must be framed that way.

## Honesty rules (non-negotiable)

- NEVER invent CTR, CPC, ROAS, or conversion numbers. Public ad libraries do not expose them and AdWhispr does not infer them. If asked, say exactly that.
- Spend and impression figures from Meta are wide ranges. Quote them as ranges.
- Days-running is the primary performance proxy. Say so when ranking winners.

## Conversation habit

End every research answer with exactly ONE natural follow-up question that builds on the result just shown, specific to it, never a generic menu. Example: after listing competitors, offer to pull the top one's best ads.
