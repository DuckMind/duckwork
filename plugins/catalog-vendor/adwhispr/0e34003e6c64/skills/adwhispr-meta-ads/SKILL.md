---
name: adwhispr-meta-ads
description: "Launch and manage Meta (Facebook and Instagram) ads from chat: single images, carousels, videos, creative tests, retargeting, and radius targeting. Use when the user wants to run, launch, edit, or manage Facebook or Instagram ads, or asks to advertise on Meta."
---

# Meta (Facebook / Instagram) ads

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll set up your Meta campaign — created paused, you approve before anything spends."
4. A free account is enough to start. After they connect, continue right where the request left off.


## Connect once

`connect_ad_account` platform meta returns a browser link (OAuth on Meta's own consent screen). Never ask for tokens in chat.

## Launching

- The user's OWN creatives: `launch_meta_ad`. One image card = single-image ad; 2-10 cards = carousel in that order; one video card = video ad; MIXED cards = a creative test (each card its own ad in one shared ad set, Meta shifts budget to the winner). Cards come from the Creative Library by creativeName (`list_my_creatives`) or a direct URL the user OWNS. Never competitor media.
- An image clone made in the AdWhispr app: `launch_cloned_ad` (clonedAdId from list_my_creatives) — the copy and link are the USER'S OWN, written fresh; competitor copy is never reused.
- Campaign-only shapes: `launch_campaign` platform meta — with a dailyBudgetUsd and objective traffic/sales/awareness/engagement it creates the campaign PLUS a targeted ad set.
- The ad runs from one of the user's Facebook Pages: pageName picks by name; one enabled page is used automatically.

## Objectives and targeting

- Objectives: traffic (default), sales (auto-attaches the account's Meta pixel, optimizes purchases; clear error if no pixel), leads, awareness, engagement. If the goal matters and is unstated, ASK.
- Targeting is opt-in: interests, ages, gender, countries/cities/regions, retargeting audiences — resolve ids with `search_ad_targeting` first (kind interests/locations/audiences/pixels; Meta also creates website-visitor and lookalike audiences). Radius targeting: radiusAddress + radiusKm.
- Editing live copy: launch_meta_ad with editAdId changes message/headline/link in place (before-vs-after preview; the ad re-enters Meta review).

## Launch safety (always applies)

- Every campaign is created PAUSED. Nothing spends until the user resumes it.
- Launch, budget, and resume tools are TWO-STEP: the first call returns a preview plus a confirmToken; show the preview, get the user's explicit OK, then call again with the same args plus that token. Never invent a token.
- `resume_campaign` starts real spend. Surface its warning and confirm before passing the token.
- If the user has not clearly stated the campaign objective, ask them to pick from the valid list instead of guessing.
- Targeting is opt-in: only set what the user asked for, resolve real ids with `search_ad_targeting` first, and never invent ids.
