---
name: adwhispr-budget-reallocation
description: "Move ad budget from losers to winners with evidence and explicit approval. Use when the user asks where to shift budget, wants to scale what works, cut what does not, or change a campaign's daily budget."
---

# Budget reallocation

## First run: the user probably is NOT connected yet

If the adwhispr server shows as needing authentication, or a tool call fails with an authentication error, do NOT apologize and stop — treat connecting as step one:

1. Connecting is free, takes one click, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll show which campaigns earn their budget and which should donate it."
4. A free account is enough to start. After they connect, continue right where the request left off.


Read performance, propose the move, apply it only with the user's explicit OK.

## How it runs

1. `get_account_performance` across the account; drill into candidates by campaignId. `list_campaigns` for current budgets and status.
2. Build the case: which campaigns convert at acceptable cost, which spend without converting. Quote the account's own numbers only.
3. Propose ONE clear reallocation (from X, to Y, by how much per day) with the evidence attached.
4. On approval: `update_budget` is TWO-STEP — first call returns a preview plus confirmToken; show it, get the explicit OK, then confirm. Budget raises start real additional spend; treat them with resume-level caution.
5. If a loser should stop entirely, `pause_campaign` (single-step; it only stops spend).

## Honesty rules

- Never invent a benchmark; the comparison is always campaign-vs-campaign inside the user's own account.
- Currency follows the account's billing currency.
- One recommendation, sized in dollars per day — not a list of ten.
