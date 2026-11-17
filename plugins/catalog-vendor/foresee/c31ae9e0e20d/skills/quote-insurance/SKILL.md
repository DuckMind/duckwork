---
# @copy skill.quote-insurance audience=agent
name: quote-insurance
description: This skill should be used when the user wants a personal lines (home, auto, or renters) insurance quote comparison or price estimate — e.g. asks "how much would car insurance cost me", "what auto insurance should I get", "estimate my renters insurance", "what would I pay for insurance on my <car>", or gives driver/vehicle/home details and asks for a price. Gathers the minimum profile conversationally and returns carrier quote estimates, with optional live confirmation from the carriers' own sites.
version: 0.8.0
---

# Quote Insurance

Return insurance quote estimates for the user by calling the `foresee` MCP tools.
Foresee returns instant, accurate, detailed quote estimates — per-carrier monthly point
estimates, full sub-coverage detail, and a per-lever price ladder — so the user can
make decisions about limits, deductibles, and so on across every carrier.
Foresee does not show ads and does not sell marketing leads.

## Scope

`quote_insurance` takes `auto`, `home`, and `renters`, and several lines in one call
price as a bundle. Foresee prices the lines and states it currently serves —
**California auto is live today**. A line that isn't live yet comes back under
`skipped` with copy saying where Foresee IS live: relay it plainly in one sentence,
never quote a different line than the user asked for, and offer a live line only if
it's relevant — once, not repeated.

## How Foresee works — two tools

1. **`quote_insurance` (instant).** Quote estimates from every carrier Foresee
   supports, with a full sub-coverage breakdown and a price ladder, in one call. This
   is the headline answer and the default path.
2. **`live_carrier_quotes` (agents).** Foresee's computer use agents complete the
   carriers' own quote flows and read back the page-printed premium, so the estimate
   can be confirmed with the carrier. Only on the agents server
   (`agents.go-foresee.com`).

Lead with 1; offer 2 when the user is ready to act on firm numbers.

## When this applies

The user wants to know what insurance would cost them, or gives details
(age, ZIP, car, home, driving record) and asks for a price/estimate/comparison.

## What to collect

The only required facts are **ZIP**, **age** (or `dob`), and — for auto — each
vehicle's **year / make / model**. They have no server-side fallback: when the user
implied one ("Sacramento", "mid-20s"), pass a concrete value and tell them the
assumption.

Everything else is optional and improves the estimate — collect what you can
conversationally, never demand it:

- **Driving record** — per driver, `auto.drivers[].accidents` / `violations` as lists
  of structured objects (an empty list is a clean record).
- `marital_status`, `gender`, `credit_range`, `home_ownership_status`,
  `prior_insurance` (insurance for the same line), `companion_policies` (insurance
  for a different line).
- `military_affiliation` — USAA sells only to military members, veterans, and their
  families; ask when it might apply.
- **Home / renters** — the `property` block (`year_built`, `construction_type`,
  `roof_type`, `replacement_cost`, …).

Omitted optional fields become **declared assumptions**: Foresee chooses a
conservative stand-in and reports it back under `assumptions`, with `tighten_by`
listing the ones that would move the price most. You can always give a number first
and sharpen it after.

## How to run it

1. Once you have the required facts, call. When the user has given (or implied) them
   plus their driving history, call in your **first** reply — price first, don't ask
   first. Only when most are missing, ask **one** round of 2–4 short questions, then
   call once.
2. Call **`quote_insurance`** with `profile` (exact field names: core `zip_code`,
   `age`/`dob`; `auto.vehicles[]`, `auto.drivers[]`; `property`) and **`lines`** —
   keys are the lines to price, values are that line's coverage options as actual
   numbers. Nothing is priced at a server default: the options you pass are the ones
   priced.
   - **auto**: `bi` (e.g. `"100/300"`), `pd` (e.g. `100`), `coll_deductible`,
     `comp_deductible`; optional `um`, `medpay`.
   - **home**: `coverage_a` (usually the replacement cost), `coverage_e`,
     `coverage_f`, `aop_deductible`. B/C/D come back in `sel` as ratios of A.
   - **renters**: `coverage_c`, `coverage_e`, `coverage_f`, `deductible`; optional
     `coverage_d`.

   If the user stated limits or deductibles, use them. Otherwise, for auto, pass the
   common starting point — `lines={"auto": {"bi": "100/300", "pd": 100,
   "coll_deductible": 500, "comp_deductible": 500}}` — on the **first** call and
   present it as the adjustable assumption it is. Several keys at once
   (`{"auto": {...}, "renters": {...}}`) price a bundle.
3. Read the result. The content channel is compact machine text, one section per
   line, with a self-describing legend:

   | Prefix | Meaning |
   |---|---|
   | `Q` | What was priced: state, line, coverage selection (`sel`) |
   | `format:` `factors:` | Legend for everything below |
   | `assumptions:` | What Foresee assumed; `high_impact: true` materially moves the estimate |
   | `tighten_by:` | The missing facts that would most move the price |
   | `not_priced:` | Carriers excluded, with the reason |
   | `C` | Carrier, writing entity, monthly point estimate, and `ci lo-hi` |
   | `W` | Warning on the carrier above — e.g. "Does not write state minimum BI / PD" |
   | `L` | Monthly cost per coverage or peril |
   | `F` | One rating factor; values align with the `L` codes. Suffix: none = exact, `~` = derived, `?` = estimated |
   | `D` | Price ladder: every offered rung of a lever as ±$/mo vs the quoted monthly, everything else held |
   | `B` | Bundle: carrier, bundled $/mo, standalone $/mo, savings |

   structuredContent carries the headline per line under `by_line` (`carriers[]` with
   `monthly`, `confidence_interval`, `carrier_quote_url`, `warnings`; plus
   `assumptions`, `tighten_by`, `failures`), and `bundle` / `skipped` at the top.

## The two kinds of uncertainty — keep them separate

- **Confidence interval = irreducible.** What Foresee genuinely can't resolve — e.g.
  which of a carrier's writing entities the user would be placed in (a `ci` segment
  on the `C` row is that placement span). `confidence_interval` is
  `{low, high, confidence, basis}`, or `{confidence: "unmeasured"}` when there is
  nothing to bound. Report it as confidence, not a hedge, and **never widen it**
  because the profile was thin.
- **`assumptions` / `tighten_by` = reducible.** Fields the user didn't give. Still
  give the point estimate; then name the one or two `tighten_by` facts that would
  sharpen it and offer to re-quote with the answers, sent under the matching
  assumption's `path`.

So: incomplete profile → **point estimate + name the assumptions**, never a wider range.

## Presenting results

- **Open with the decision.** The best option for this user — its price and a
  one-line reason.
- Then a comparison sorted **cheapest-first**: **Carrier · Monthly · 6-month total**
  (a markdown table when the surface renders it), and the **annual dollar spread**
  between cheapest and priciest — that spread is the reason to compare.
- These are Foresee's **estimates** of what each carrier will charge — say so, and
  let `assumptions` / `tighten_by` explain how they were made and how to sharpen them.
- Relay every `W` warning and every `not_priced` carrier with its reason (e.g. USAA
  for a household that isn't military-affiliated) — a carrier never silently vanishes.
- **Bundles:** a `B` row's per-line prices assume every bundled line is placed with
  that carrier; for a cross-carrier mix, compare standalone totals.
- End on the next concrete action — the recommended carrier's `carrier_quote_url`, or
  an offer to confirm live (below).

## Live quotes from the carrier's own site — `live_carrier_quotes`

When the user wants to confirm the estimate with the carrier, Foresee's agents
complete the carriers' real quote flows and read back the page premium. Hypothetical
profiles work too; when the details are the user's real ones, the consent below is
what makes the submission theirs to authorize.

**Arguments**

- `profile` — the same rating facts as `quote_insurance`.
- `lines` — one key per line to walk, each value that line's ask:
  - `auto` — **required**: the same four axes as `quote_insurance`, as actual numbers.
  - `home` — **none**: `{"home": null}`. The carrier's own form prices its package;
    the agents report what it chose. A supplied ask is refused (`bad_ask`).
  - `renters` — **required**: `coverage_c`, `coverage_e`, `coverage_f`, `deductible`,
    as actual dollars.

  Several keys at once commission bundled walks: each carrier that writes all the
  named lines is driven through its own multi-line quote flow and reports per-line
  premiums plus its own bundle total; a carrier writing only some of the lines is
  walked for those alone.
- `user_authorization` — the user's in-chat go-ahead, **verbatim**.
- `identity` — usually required: `first_name`, `last_name`, `dob`, `street`, `city`,
  `email` (carriers send the quote here); optional `unit`, `phone`, and `zip_code`
  only when it differs from the profile's. Collect it in chat. **Never an SSN.** A
  driver's licence number goes on that driver's `auto.drivers[].drivers_license_number`,
  and only when a carrier's `needs` entry asks for it.
- `carriers` — optional; defaults to every carrier with a validated walk.

**Consent — before the first call**

1. Tell the user plainly: Foresee will submit their details to the named carriers;
   the carriers may obtain their credit-based insurance score (a soft pull, no
   impact on their credit score); and the carriers may contact them by email or phone.
2. Get their explicit go-ahead and pass it verbatim as `user_authorization` (e.g.
   "yes, go ahead"). It is stored as the consent record before any carrier sees the
   details. No sign-in is needed.

**Collecting results**

The tool is idempotent: the first call commissions the agents; re-call with the
**same arguments** after a minute or two to collect progress and results — nothing is
re-submitted, and a profile already walked returns those results. Read:

- `status` — `in_progress` / `partial` / `complete`; `note` says what to do next.
- `agents[]` — per carrier: `stage` and `eta_seconds_remaining` while working; when
  quoted, `quote.premium` **verbatim as the page printed it** and `quote.term_months`
  (the term it covers — $857.80 per 6 months is not per month; show the monthly
  equivalent beside the page's own figure). Also `premium_by_line` (bundled walks),
  `breakdown`, `bound`, `variants`, `quote_number`.
- `declined: true` — the carrier reviewed the details and refused to quote. **An
  answer, not an error** — relay it.
- `confirmation` — per carrier, the instant estimate beside the page-printed premium
  (the bundle estimate when several lines were walked). Present the two side by side
  with the delta.
- `skipped` / `not_dispatched` — carriers not walked, each with the reason. Relay them.
- `assumptions` — minor form facts the walks answered with declared no-claim values
  (`field` + `assumed`). Relay every one; if the user corrects one, re-call with the
  real value at that path.

**Refusals** are structured `{"error", "detail"}` — nothing reached a carrier unless
noted:

| Code | What to do |
|---|---|
| `authorization_required` | Give the disclosure, get a yes, pass it verbatim |
| `missing_facts` | Ask the user for exactly the `needs[].fields[]` facts (use their `values` where given) and re-call |
| `coverage_selection_required` | Re-call with the full auto/renters numbers |
| `bad_ask` | Send `{"home": null}` |
| `profile_required` | Wrap the facts in `profile` |
| `bad_profile` / `bad_identity` | Fix the field `detail` names |
| `unknown_line` | Use a line from `detail` |
| `no_carriers` | Fall back to `quote_insurance` |
| `launch_failed` | Nothing reached any carrier — retrying is safe |

## Finishing up — hand off to the carrier

Foresee only collects quotes; it does not take payment or bind insurance. When the
user settles on a carrier (or asks to buy), give that carrier's **`carrier_quote_url`**
as a clickable link on its own line — the purchase completes on the carrier's own
quoting portal.

## The one hard rule: never invent a price

Only state numbers the result contains, or `monthly` + a `D` delta. Answer a
single-lever what-if ("what would a $1000 deductible cost?") straight from `D` — don't
re-call. If a rung shows `(asked X)`, X isn't offered and the price sits at the nearest
offered rung — say so. **Do not** multiply `F` factors, interpolate between rungs, or
average carriers. For a change to several levers at once, or a carrier not returned,
re-call with the new ask in `lines`.
