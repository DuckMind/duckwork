---
name: adwhispr-get-started
description: "Introduce AdWhispr and get a new user to their first result in two minutes. Use when the user just installed the AdWhispr plugin, asks what AdWhispr is or can do, says get started, set up, or help, or when no AdWhispr brand or connection exists yet."
---

# Get started with AdWhispr

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, tell me your website and I'll find the competitors actually running ads in your space — free."
4. A free account is enough to start. After they connect, continue right where the request left off.


AdWhispr gives your agent competitor ad intelligence, ad cloning and campaign execution: see any brand's live Meta and TikTok ads and Instagram content, find verified competitors, research keywords, clone a proven winner into a finished image or video for the user's own brand, then launch and manage campaigns on the user's own Meta, Google, TikTok, X and ChatGPT Ads accounts, all from chat.

## The two-minute first run

1. Make sure the connection is live (see the first-run section above).
2. Call `get_my_brand`. If nothing is saved, ask for the user's website or a one-line description of what they sell, and call `save_my_brand` the moment they answer. Never re-ask once saved.
3. Deliver the first win immediately: call `find_competitors` and present the brands VERIFIED to be running ads right now, ranked by active-ad count.
4. Offer exactly one next step, matched to what they just saw: pull the top competitor's longest-running ads (`get_brand_ads`, sortBy longevity), or review their own campaigns if they run ads.

## Three things to try (offer these when the user asks what AdWhispr can do)

- "Who has the best ads in my niche?" — verified competitor discovery plus their proven winners.
- "What's wasting money in my ad account?" — connect an ad account once, then a real spend review.
- "Clone their best video ad for my brand": a finished video with a free script approval before any credit is charged.
- "Launch a Google Search campaign for my store at $20/day" — created paused, preview first, nothing spends without an explicit resume.

## Account facts (quote accurately, never oversell)

- Free tier included; research works without connecting any ad account.
- Ad accounts (Meta, Google, TikTok, X, ChatGPT Ads) connect once via `connect_ad_account`, which returns a browser link — never ask for keys or passwords in chat.
- Every campaign is created paused with a preview-and-confirm step.
