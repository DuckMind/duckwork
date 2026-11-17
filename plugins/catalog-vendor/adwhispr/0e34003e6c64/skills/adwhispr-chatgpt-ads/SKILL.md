---
name: adwhispr-chatgpt-ads
description: "Launch and manage ChatGPT ads (OpenAI Ads) from chat: chat-card ads with context-hint targeting inside ChatGPT. Use when the user wants to advertise on ChatGPT, run OpenAI ads, or asks whether ads inside ChatGPT are possible."
---

# ChatGPT Ads (OpenAI)

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll stage a ChatGPT ad campaign — chat card, targeting hints and all, paused until you approve."
4. A free account is enough to start. After they connect, continue right where the request left off.


Yes — ads inside ChatGPT are real, and AdWhispr launches them.

## Connect once (different from other platforms)

The customer's OpenAI Ads API key IS the credential: created in OpenAI Ads Manager (Settings), then pasted on AdWhispr's secure connect page. `connect_ad_account` platform chatgpt returns the LINK to that page. NEVER ask the user to paste the key into the chat.

## Launching

`launch_campaign` platform chatgpt builds campaign + ad group + the ad (a ChatGPT chat card) together, all paused:
- dailyBudgetUsd is REQUIRED; the objective must be traffic, sales, or leads (all run as Maximize clicks — OpenAI sets the bid). Awareness/engagement/app/video are refused, not silently changed.
- adTitle: the headline, 3-50 characters, written fresh for the user's own product.
- adBody: up to 100 characters.
- imageUrl: a direct https image at least 640x640 the user OWNS, or the exact name/id of an image in their Creative Library (`list_my_creatives`).
- landingUrl defaults to the user's saved website.
- keywords become the ad group's CONTEXT HINTS: short descriptions of the moments the ad is useful (e.g. "lightweight trail shoes for rocky terrain") — that is how ChatGPT decides relevance; they are not exact-match keywords.
- Geo: countries (ISO-2) and/or locationIds from `search_ad_targeting` platform chatgpt kind locations.

## Expectations to set

- Every new ad goes through OpenAI's review before it can serve.
- Resume wakes paused ad groups and ads and notes review blockers plainly.

## Launch safety (always applies)

- Every campaign is created PAUSED. Nothing spends until the user resumes it.
- Launch, budget, and resume tools are TWO-STEP: the first call returns a preview plus a confirmToken; show the preview, get the user's explicit OK, then call again with the same args plus that token. Never invent a token.
- `resume_campaign` starts real spend. Surface its warning and confirm before passing the token.
- If the user has not clearly stated the campaign objective, ask them to pick from the valid list instead of guessing.
- Targeting is opt-in: only set what the user asked for, resolve real ids with `search_ad_targeting` first, and never invent ids.
