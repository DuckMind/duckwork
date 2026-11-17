---
name: adwhispr-x-ads
description: "Launch and manage X (Twitter) ads from chat: promoted posts, creative tests, keyword and interest targeting, conversions. Use when the user wants to run ads on X or Twitter, promote a post, or manage X campaigns."
---

# X (Twitter) ads

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll stage your X campaign with the promoted post built in — paused until you approve."
4. A free account is enough to start. After they connect, continue right where the request left off.


## Connect once

`connect_ad_account` platform x returns a browser link. Never ask for tokens in chat.

## Prerequisites X enforces (tell the user up front when relevant)

- A payment method added at ads.x.com (funding cannot be set up via API).
- X Premium or Verified Organizations on the advertising handle.

## Launching

`launch_campaign` platform x — dailyBudgetUsd is REQUIRED. Creative in the same call:
- postText and/or imageUrl builds the campaign, its ad group, AND the promoted post together, all paused.
- posts (2+ entries) runs a creative test: each post becomes its own ad in one ad group and X shifts budget to the winner.
- With no post content it creates campaign + ad group only, and the user adds the post in X Ads Manager.
- landingUrl is appended so X builds a link card.

## Targeting and conversions

- Same-call params: countries (ISO-2), gender, ageMin/ageMax (X uses one age bucket), keywords (X keyword targeting, broad match). Interests/locations/audiences/web-event-tags via `search_ad_targeting` platform x. Never invent ids.
- A sales or leads objective optimizes for conversions on the account's web event tag (X's pixel), auto-picked; with no tag it runs optimized for website clicks and the reply says so.

## Launch safety (always applies)

- Every campaign is created PAUSED. Nothing spends until the user resumes it.
- Launch, budget, and resume tools are TWO-STEP: the first call returns a preview plus a confirmToken; show the preview, get the user's explicit OK, then call again with the same args plus that token. Never invent a token.
- `resume_campaign` starts real spend. Surface its warning and confirm before passing the token.
- If the user has not clearly stated the campaign objective, ask them to pick from the valid list instead of guessing.
- Targeting is opt-in: only set what the user asked for, resolve real ids with `search_ad_targeting` first, and never invent ids.
