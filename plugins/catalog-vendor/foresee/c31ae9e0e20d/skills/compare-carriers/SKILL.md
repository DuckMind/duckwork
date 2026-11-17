---
# @copy skill.compare-carriers audience=agent
name: compare-carriers
description: This skill should be used when the user wants to compare personal lines insurance carriers, shop around, or find the right insurance — e.g. "compare car insurance companies", "who is cheapest for me", "is GEICO or Progressive cheaper", "should I switch from State Farm".
version: 0.8.0
---

# Compare Carriers

Help the user shop for insurance by ranking carriers for their profile using the
`foresee` MCP tools, and — when it matters — reasoning about *how the coverage is set
up*, because the cheapest carrier changes with the coverage selection.

## When this applies

The user wants a side-by-side of carriers, asks who is cheapest, names two carriers
to compare, is deciding whether to switch, or wants to trade coverage against price.

## How to run it

1. Gather the profile (see the `quote-insurance` skill). ZIP, age (or `dob`) and, for
   auto, each vehicle's year/make/model are required; the rest sharpens the estimate.
2. If the user named specific carriers, pass them via `carriers` (keys like `geico`,
   `progressive`, `statefarm`, `allstate`, `libertymutual`, `mercury`, `farmers`,
   `travelers`, `usaa`). Otherwise omit it — it defaults to all carriers.
3. Call **`quote_insurance`** with `lines` naming each line and its coverage options
   as actual numbers — for auto, the user's limits or the common start:
   `lines={"auto": {"bi": "100/300", "pd": 100, "coll_deductible": 500,
   "comp_deductible": 500}}`, declared as an adjustable assumption. Each carrier comes
   back with a `C` row (monthly point estimate and `ci`), `L` per-coverage lines, `D`
   price ladders, any `W` warnings, and `carrier_quote_url`; carriers that couldn't
   be priced are in `not_priced:` with the reason. A line that isn't live yet comes
   back under `skipped` — relay it.
4. When the user wants to confirm the estimates with the carriers, offer
   **`live_carrier_quotes`** (agents server only): Foresee's agents complete the
   carriers' own quote flows and read back the page-printed premium, with a
   `confirmation` block beside the estimate. Consent comes first — see the
   `quote-insurance` skill for the disclosure and the verbatim `user_authorization`.
   Re-call with the same arguments to collect; fold completed quotes into the
   comparison and call out anything now cheaper than the previous best. A carrier
   that `declined` is a real answer — relay it.

## Presenting results

- **Rank by the monthly point estimate**, cheapest first.
- Show a compact table: **Carrier · Monthly · 6-month total** (plus the interval when
  it matters), and the annual dollar spread between cheapest and priciest — that
  spread is the reason to compare.
- **Ties within the interval are noise.** If two carriers' point estimates fall
  inside each other's `confidence_interval`, say they're effectively tied rather than
  declaring a $3/mo "winner".
- Relay every `not_priced` carrier and `W` warning rather than silently dropping them.
- These are Foresee's estimates of what each carrier will charge — say so.

## Reasoning about the coverage ladder across carriers

The ranking can flip with the coverage selection. A carrier that's cheapest at a $500
collision deductible may not be cheapest at $1000, and limits behave the same way.

- **Read `D` first.** Each carrier's ladder gives every offered rung of each lever as
  ±$/mo against its monthly, everything else held — so "who's cheapest at a $1000
  deductible?" is a direct read across carriers, with no extra call.
- **`(asked X)`** on a rung means X isn't offered by that carrier and the price sits
  at the nearest offered rung — say so rather than implying the carriers were priced
  at the same rung.
- **Re-call for a combined change** — when the user pins several levers at once,
  re-call with the full ask at the new rungs and compare the new monthlies.
- This is how you surface statements like *"Liberty Mutual is cheapest at a low
  deductible, but you want a high one, so GEICO wins for you."*

## Bundles

Pass several keys in `lines` (e.g. `{"auto": {...}, "renters": {...}}`) to price a
bundle. A `B` row gives a carrier's bundled $/mo, standalone $/mo, and savings; its
per-line prices assume every bundled line is placed with that carrier. For a
cross-carrier mix (auto with one, renters with another), compare standalone totals.

## The one hard rule: never invent a price

Rank, filter, and pivot only over numbers Foresee returned, or `monthly` + a `D`
delta. **Do not** multiply `F` factors, interpolate a rung, or synthesize one
carrier's number from another's. For another carrier or coverage combination, call
the tool again.

## Honesty guardrails

- Do not invent carriers or prices. If a carrier isn't priced, say so and why.
- USAA sells only to military members, veterans, and their families — flag it when
  it appears and the user isn't eligible.
- Foresee does not take payment or bind insurance; when the user wants to buy, give
  the carrier's `carrier_quote_url` as a clickable link.
