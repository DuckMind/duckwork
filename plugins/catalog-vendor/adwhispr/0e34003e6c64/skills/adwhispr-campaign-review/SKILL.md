---
name: adwhispr-campaign-review
description: "Review the user's own ad campaign performance and manage running campaigns. Use when the user asks how their campaigns are doing, wants spend, clicks, or conversion numbers, wants a weekly or Monday review, or wants to pause, resume, or change the budget of a campaign."
---

# Campaign performance review and management

## First run: the user probably is NOT connected yet

Most people who installed the AdWhispr plugin have not signed in to AdWhispr. If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one of the workflow:

1. Say it plainly and positively: connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them exactly what happens the moment they are connected: "the second you're connected, I'll pull your real spend, clicks and conversions and flag the single change that matters most this week." (Reviewing their own ad accounts also needs an ad account connected once via connect_ad_account — same pattern: offer the link, never ask for keys in chat.)
4. A free account is enough to start. After they connect, continue the workflow right where it left off — do not make them repeat their request.


These tools act on the USER'S OWN connected ad accounts (Meta, Google, TikTok), never on competitor data.

## The review

1. `list_ad_accounts` to see what is connected. If nothing is, `connect_ad_account` returns the browser link to connect one.
2. `get_account_performance` pulls real spend, impressions, clicks, and conversions. Pass a campaignId to drill into one campaign, including Google keyword-level diagnostics.
3. `list_campaigns` shows everything running with status and budget.

Report only numbers the tools return. Currency follows the ad account's own billing currency, and outputs label it when it is not USD.

A good review answers three questions in plain language: what is spending, what is converting, and what single change matters most this week. Make one concrete recommendation, not a list of ten.

## Making changes

- `update_budget`, `pause_campaign`, `resume_campaign`, `update_campaign_locations` (Google), `update_keywords` and `add_negative_keywords` (Google, when available).
- Budget changes and resumes are TWO-STEP: preview plus confirmToken first, execute only after the user's explicit OK.
- `resume_campaign` starts real spend. Always surface the warning.
- `pause_campaign` is single-step since it only stops spend.

## Recurring reviews

There is no scheduler in this connection, but two good habits work well:
- The user can simply ask for a review any time ("Monday review, please") and you run the workflow fresh.
- For automatic weekly competitor digests by email, AdWhispr Pro members can flip the toggle at https://adwhispr.com/dashboard/settings?utm_source=duckwork&utm_medium=plugin&utm_campaign=duckwork_plugin under Email Alerts. That digest covers tracked competitors' ad changes, not the user's own campaign numbers.
