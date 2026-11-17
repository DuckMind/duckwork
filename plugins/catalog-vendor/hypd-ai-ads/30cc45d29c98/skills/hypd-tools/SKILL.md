---
name: hypd-tools
description: How HYPD's tools work and the rules to respect when calling them. Use at the start of every session that uses HYPD, and whenever a HYPD tool returns a validation error.
---

# Using HYPD's tools

**Call `init` once at the start of each session, before other HYPD tools.** It returns HYPD's getting-started reference: supported platforms, account ID formats, how the tool groups relate, and plan status.

## Read-only

- **HYPD's tools only read.** Nothing creates, edits, pauses or deletes anything in a connected platform. Report what the data shows; never say an action was taken.

## Rules the tools enforce

- **Google Ads account IDs are 10 digits with no dashes** (`2712366093`, never `271-236-6093`). Get them from `google_ads_list_accounts`.
- **`google_ads_run_gaql` on `change_event`** needs a `change_date_time` filter within the last 30 days and a `LIMIT`. Older change history does not exist.
- **GA4 realtime reports** cannot combine most dimensions with metrics.
- **LinkedIn tools:** call them one at a time, never in parallel.
- **Research tools** (keywords, SERP, competitor ads) need a country and a language. Ask if the market is unclear.
- **Cap list-style requests** (top 5 or 10) so responses stay fast.
- **Report tool errors as errors.** Never fill gaps with data a tool did not return.

## Reference material on the server

- `list_skills` and `load_skill` return HYPD's methodology guides (checklists and definitions for topics such as wasted-spend review). Treat them as background reading for the analysis the user asked for.
- `prompt_templates_list` and `prompt_templates_get` return HYPD's saved analysis templates as text. See the **hypd-workflows** skill.

If no accounts come back or a tool reports an authentication problem, follow the **hypd-getting-started** skill.
