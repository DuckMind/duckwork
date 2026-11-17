---
name: seo-flow
description: "Apply the FLOW framework to SEO planning."
author: Daniel Agrici
license: CC BY 4.0
---

# FLOW Framework: Find · Leverage · Optimize · Win

FLOW is an evidence-led SEO operating model built for the AI-search era. Duckwork SEO
integrates the FLOW prompt library (41 prompts across 5 stages) so every analysis can
be driven by structured, evidence-backed AI prompts rather than improvised queries.

> Framework and prompts © Daniel Agrici, CC BY 4.0: github.com/AgriciDaniel/flow

**Runtime context:** Load `references/flow-framework.md` on every `duckwork-seo:seo-flow` activation.
Load prompt files on demand, only for the stage the user requests.

---

## Commands

| Command | What it does |
|---------|-------------|
| `duckwork-seo:seo-flow` | Show FLOW overview + stage menu |
| `duckwork-seo:seo-flow find [url\|topic]` | Find-stage: keyword research, gap analysis, SERP intent mapping (5 prompts) |
| `duckwork-seo:seo-flow leverage [url]` | Leverage-stage: backlink strategy, off-site authority (1 prompt) |
| `duckwork-seo:seo-flow optimize [url]` | Optimize-stage: select 2-3 most relevant of 21 prompts based on context |
| `duckwork-seo:seo-flow win [url]` | Win-stage: BOFU, conversion rate, dual-surface scorecard (3 prompts) |
| `duckwork-seo:seo-flow local [url]` | Local-stage: GBP optimization, meta, title tags, local audits (11 prompts) |
| `duckwork-seo:seo-flow prompts` | Full index of all 41 prompts (stage, name, trigger conditions) |
| `duckwork-seo:seo-flow sync` | Pull latest prompt files from github.com/AgriciDaniel/flow |

---

## Orchestration Logic

### On `duckwork-seo:seo-flow` (no sub-command)
1. Load `references/flow-framework.md` with `skill_view(name="duckwork-seo:seo-flow", file_path="references/flow-framework.md")`.
2. Show the FLOW stage overview with a one-line description of each stage
3. Ask: which stage matches the user's current situation?

### On `duckwork-seo:seo-flow find [url|topic]`
1. Load `references/prompts/README.md` with `skill_view`, then load each find-stage file with `skill_view(name="duckwork-seo:seo-flow", file_path="references/prompts/find/<prompt-file>.md")`.
2. Apply each prompt to the URL or topic
3. Cross-reference: "For deeper SERP clustering, see `duckwork-seo:seo-cluster <seed-keyword>`"

### On `duckwork-seo:seo-flow leverage [url]`
1. Load the leverage prompt with `skill_view(name="duckwork-seo:seo-flow", file_path="references/prompts/leverage/<prompt-file>.md")`.
2. Apply to the URL's current backlink context
3. Cross-reference: "For raw backlink data, see `duckwork-seo:seo-backlinks <url>`"

### On `duckwork-seo:seo-flow optimize [url]`
1. Load `references/prompts/README.md` with `skill_view` to see the optimize prompt filenames.
2. Use prior analysis context from this conversation (URL, industry vertical, and any earlier skill output).
3. Select 2-3 most relevant prompts; load only those files
4. Apply selected prompts; note the others are accessible via `duckwork-seo:seo-flow prompts`
5. Cross-reference: "For full content quality analysis, see `duckwork-seo:seo-content <url>` and `duckwork-seo:seo-geo <url>`"

### On `duckwork-seo:seo-flow win [url]`
1. Load `references/prompts/README.md` with `skill_view`, then each win-stage prompt with `skill_view(name="duckwork-seo:seo-flow", file_path="references/prompts/win/<prompt-file>.md")`.
2. Apply each prompt to the URL's conversion and BOFU context
3. Cross-reference: "For SXO persona scoring, see `duckwork-seo:seo-sxo <url>`"

### On `duckwork-seo:seo-flow local [url]`
1. Load `references/prompts/README.md` with `skill_view`, then each local-stage prompt with `skill_view(name="duckwork-seo:seo-flow", file_path="references/prompts/local/<prompt-file>.md")`.
2. Apply to the URL's local SEO context
3. Cross-reference: "For full local SEO analysis, see `duckwork-seo:seo-local <url>` and `duckwork-seo:seo-maps [command]`"

### On `duckwork-seo:seo-flow prompts`
1. Load `references/prompts/README.md` with `skill_view(name="duckwork-seo:seo-flow", file_path="references/prompts/README.md")`.
2. Display the full index: all 41 prompts with stage, name, trigger conditions

### On `duckwork-seo:seo-flow sync`
1. Run: `duckwork seo run sync_flow.py`
2. Display the JSON summary (files added, updated, unchanged)
3. Show attribution notice after sync completes

---

## Context Matching (Optimize stage)

The optimize stage has 21 prompts. Dumping all 21 is noise. Select by priority:

1. **Industry vertical** (SaaS → on-page + technical; local → citations + GBP; publisher → E-E-A-T + freshness)
2. **Prior skill output** (seo-technical flagged crawl issues → technical optimize prompts; seo-content flagged E-E-A-T gaps → content optimize prompts)
3. **URL signals** (product pages → conversion; blog → freshness + authority)

Always surface exactly 2-3 prompts. State which prompts you chose and why.

---

## Reference Files

Load on-demand, do NOT load all at startup:
- `references/flow-framework.md`: FLOW operating model (load on every `duckwork-seo:seo-flow` activation)
- `references/bibliography.md`: Evidence sources; load when citing studies or statistics
- `references/prompts/README.md`: Prompt index; load for `duckwork-seo:seo-flow prompts`
- `references/prompts/find/`: 5 prompts; load for `duckwork-seo:seo-flow find`
- `references/prompts/leverage/`: 1 prompt; load for `duckwork-seo:seo-flow leverage`
- `references/prompts/optimize/`: 21 prompts; load selectively for `duckwork-seo:seo-flow optimize`
- `references/prompts/win/`: 3 prompts; load for `duckwork-seo:seo-flow win`
- `references/prompts/local/`: 11 prompts; load for `duckwork-seo:seo-flow local`

---

## Attribution

Every `duckwork-seo:seo-flow` activation (any sub-command) outputs before analysis:

```
Framework and prompts © Daniel Agrici, CC BY 4.0: github.com/AgriciDaniel/flow
```

Do not omit or modify the attribution.

---

## Error Handling

| Scenario | Action |
|----------|--------|
| `references/flow-framework.md` missing | "FLOW reference files not synced. Run: `duckwork-seo:seo-flow sync`" |
| Prompt file missing | "Run `duckwork-seo:seo-flow sync` to pull the latest prompts from the FLOW repo." |
| `sync_flow.py` network error | Display the script's stderr. Check rate limits: `gh api rate_limit`. |
| `sync_flow.py` auth error | Run `gh auth login` then retry. |
