---
# @copy skill.explain-coverage audience=agent
name: explain-coverage
description: This skill should be used when the user asks what home, auto, or renters insurance coverage means or which limits/deductibles to choose — e.g. "what does 100/300 mean", "explain liability vs full coverage", "what deductible should I pick", "what is coverage A", "what coverage do I need in <state>", or wants to understand how changing a limit or deductible changes the price.
version: 0.7.0
---

# Explain Coverage

Explain insurance coverage terms, limits, and deductibles in plain language, grounded
in the per-coverage detail the `foresee` MCP tools return — and, when it helps, show
the user what a coverage change actually costs.

## When this applies

The user is confused about coverage terminology, limits (e.g. `100/300/100`),
deductibles, or which coverage level to carry, or asks how changing coverage affects
their price.

## The coverage options

**Auto**
- `bi` — **Bodily injury liability**: injuries you cause to other people.
  Per-person/per-accident limit in $000s — `"100/300"` = $100k per person, $300k per
  accident.
- `pd` — **Property damage liability**: damage you cause to other people's cars and
  property. Limit in $000s.
- `coll_deductible` — **Collision**: damage to your own car from a crash, whoever is
  at fault. The deductible you pay per claim.
- `comp_deductible` — **Comprehensive**: damage to your own car from anything other
  than a crash — theft, fire, hail, vandalism, hitting an animal.
- `um` — **Uninsured/underinsured motorist**: your injuries when the at-fault driver
  has no or too little insurance.
- `medpay` — **Medical payments**: medical bills for you and your passengers, whoever
  is at fault.

**Home**
- `coverage_a` — **Dwelling**: rebuilding the house itself; usually the replacement cost.
- B (other structures), C (personal property), D (loss of use) — priced as ratios of A.
- `coverage_e` — **Personal liability**: injuries or damage you're legally
  responsible for, on or off the property.
- `coverage_f` — **Medical payments to others**: a guest's medical bills after an
  injury on your property.
- `aop_deductible` — **All-other-perils deductible**: what you pay per claim for
  everything except perils with their own deductible (such as earthquake).

**Renters**
- `coverage_c` — **Personal property**: your belongings.
- `coverage_e`, `coverage_f` — liability and guest medical, as for home.
- `deductible` — what you pay per claim before coverage starts.
- `coverage_d` — **Loss of use**: extra living costs if you have to move out while
  the place is repaired.

## How to run it

1. If the question is state- or carrier-specific, ground it with
   **`quote_insurance`**. Pass the ask in `lines` as actual numbers — the user's
   limits, or for auto the common start: `lines={"auto": {"bi": "100/300", "pd": 100,
   "coll_deductible": 500, "comp_deductible": 500}}`.
2. Explain the concepts the user asked about, defining jargon the first time it
   appears.
3. When a quote is in play, ground it in that user's numbers: each carrier's `L` row
   shows every coverage's own monthly at the selection you passed — so "what am I
   paying for collision?" has a concrete answer, not just a definition.

## The coverage ladder — where the money moves

**Coverage is a ladder, and moving a rung changes both what you're covered for and
what you pay.** Raise a deductible and the premium drops (you keep more risk); raise a
limit and it rises (you offload more).

- Show the delta, don't just assert it. Each carrier's `D` row lists every offered
  rung of a lever as ±$/mo against its monthly, everything else held — "a $1000
  collision deductible saves $X/mo for $500 more exposure per claim."
- Deductibles and liability limits are separate decisions: deductibles follow the
  user's cash buffer, liability limits follow their assets.
- Offer only the rungs a carrier offers. `(asked X)` means X isn't offered and the
  price sits at the nearest offered rung. Carriers offer different ladders, and the
  best carrier can change with the rung — if the user is optimizing a specific
  coverage level, hand off to `compare-carriers`.
- For several levers at once, re-call `quote_insurance` with the full ask at the new
  rungs and compare the returned monthlies.

## The one hard rule: never invent a price

Every number you show must be one Foresee returned, or `monthly` + a `D` delta. Do not
estimate a coverage change by multiplying `F` factors or interpolating — re-call the
tool with the new ask and report what it prices. Definitions can be general; **dollars
must come from Foresee.**

## Guardrails

- A `W` warning like "Does not write state minimum BI / PD" means that carrier
  doesn't offer the asked limit — relay it. If you're unsure of a state's legal
  minimum, say so rather than stating a number you can't verify.
- Keep it practical and short.
