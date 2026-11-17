---
name: seo-cluster
description: "Plan semantic keyword clusters and content architecture."
author: Daniel Agrici
license: MIT
---

# Semantic Topic Clustering

SERP-overlap-driven keyword clustering for content architecture. Groups keywords
by how Google actually ranks them (shared top-10 results), not by text similarity.
Designs hub-and-spoke content clusters with internal link matrices and generates
interactive cluster map visualizations.

**Scripts:** Located at the plugin root `scripts/` directory.

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `duckwork-seo:seo-cluster plan <seed-keyword>` | Full planning workflow: expand, cluster, architect, visualize |
| `duckwork-seo:seo-cluster plan --from strategy` | Import from existing `duckwork-seo:seo-plan` output |
| `duckwork-seo:seo-cluster execute` | Execute plan: create content with an available writing skill or output briefs |
| `duckwork-seo:seo-cluster map` | Regenerate the interactive cluster visualization |

---

## Planning Workflow

### Step 1: Seed Keyword Expansion

Expand the seed keyword into 30-50 variants using web_search:

1. **Related searches**: Search the seed, extract "related searches" and "people also search for"
2. **People Also Ask (PAA)**: Extract all PAA questions from SERP results
3. **Long-tail modifiers**: Append common modifiers: "best", "how to", "vs", "for beginners", "tools", "examples", "guide", "template", "mistakes", "checklist"
4. **Question mining**: Generate who/what/when/where/why/how variants
5. **Intent modifiers**: Add commercial modifiers: "pricing", "review", "alternative", "comparison", "free", "top"

**Deduplication:** Normalize variants (lowercase, strip articles), remove exact duplicates.
Target: 30-50 unique keyword variants. If under 30, run a second expansion pass
with the top PAA questions as seeds.

### Step 2: SERP Overlap Clustering

This is the core differentiator. Load `references/serp-overlap-methodology.md` for
the full algorithm.

**Process:**
1. Group keywords by initial intent guess (reduces pairwise comparisons)
2. For each candidate pair within a group, web_search both keywords
3. Count shared URLs in the top 10 organic results (ignore ads, featured snippets, PAA)
4. Apply thresholds:

| Shared Results | Relationship | Action |
|---------------|-------------|--------|
| 7-10 | Same post | Merge into single target page |
| 4-6 | Same cluster | Group under same spoke cluster |
| 2-3 | Interlink | Place in adjacent clusters, add cross-links |
| 0-1 | Separate | Assign to different clusters or exclude |

**Optimization:** With 40 keywords, full pairwise = 780 comparisons. Instead:
- Pre-group by intent (4 groups of ~10 = 4 x 45 = 180 comparisons)
- Only cross-check group boundary keywords
- Skip pairs where both are long-tail variants of the same head term (assume same cluster)

**DataForSEO integration:** If DataForSEO MCP is available, use `serp_organic_live_advanced`
instead of web_search for SERP data. Run `duckwork seo run dataforseo_costs.py check serp_organic_live_advanced --count N`
before each batch. If `"status": "needs_approval"`, show cost estimate and ask user.
If `"status": "blocked"`, fall back to web_search.

### Step 3: Intent Classification

Classify each keyword into one of four intent categories:

| Intent | Signals | Include in Clusters? |
|--------|---------|---------------------|
| Informational | how, what, why, guide, tutorial, learn | Yes |
| Commercial | best, top, review, comparison, vs, alternative | Yes |
| Transactional | buy, price, discount, coupon, order, sign up | Yes |
| Navigational | brand names, specific product names, login | No (exclude) |

Remove navigational keywords from clustering. Flag borderline cases for
manual review. Keywords can have mixed intent (e.g., "best CRM software" is
both commercial and informational) -- classify by dominant intent.

### Step 4: Hub-and-Spoke Architecture

Load `references/hub-spoke-architecture.md` for full specifications.

**Design the cluster structure:**

1. **Select the pillar keyword**: Highest volume, broadest intent, most SERP overlap with other keywords
2. **Group spokes into clusters**: Each cluster is a subtopic area (2-5 clusters per pillar)
3. **Assign posts to clusters**: Each cluster gets 2-4 spoke posts
4. **Select templates per post**: Based on intent classification:

| Intent Pattern | Template Options |
|---------------|-----------------|
| Informational (broad) | ultimate-guide |
| Informational (how) | how-to |
| Informational (list) | listicle |
| Informational (concept) | explainer |
| Commercial (compare) | comparison |
| Commercial (evaluate) | review |
| Commercial (rank) | best-of |
| Transactional | landing-page |

5. **Set word count targets:**
   - Pillar page: 2500-4000 words
   - Spoke posts: 1200-1800 words

6. **Cannibalization check**: No two posts share the same primary keyword. If SERP
   overlap is 7+, merge those keywords into a single post targeting both.

### Step 5: Internal Link Matrix

Design the bidirectional linking structure:

| Link Type | Direction | Requirement |
|-----------|-----------|-------------|
| Spoke to pillar | spoke -> pillar | Mandatory (every spoke) |
| Pillar to spoke | pillar -> spoke | Mandatory (every spoke) |
| Spoke to spoke (within cluster) | spoke <-> spoke | 2-3 links per post |
| Cross-cluster | spoke -> spoke (other cluster) | 0-1 links per post |

**Rules:**
- Every post must have minimum 3 incoming internal links
- No orphan pages (every post reachable from pillar in 2 clicks)
- Anchor text must use target keyword or close variant (no "click here")
- Link placement: within body content, not just navigation/sidebar

Generate the link matrix as a JSON adjacency list:
```json
{
  "links": [
    { "from": "pillar", "to": "cluster-0-post-0", "type": "mandatory", "anchor": "keyword" },
    { "from": "cluster-0-post-0", "to": "pillar", "type": "mandatory", "anchor": "keyword" }
  ]
}
```

### Step 6: Interactive Cluster Map

Generate `cluster-map.html` using the template at `templates/cluster-map.html`.

1. read_file the template file
2. Build the `CLUSTER_DATA` JSON object from the cluster plan:
   ```javascript
   {
     pillar: { title, keyword, volume, template, wordCount, url },
     clusters: [{ name, color, posts: [{ title, keyword, volume, template, wordCount, url, status }] }],
     links: [{ from, to, type }],
     meta: { totalPosts, totalClusters, totalLinks, estimatedWords }
   }
   ```
3. Replace the `CLUSTER_DATA` placeholder in the template with the actual JSON
4. write_file the completed HTML file to the output directory
5. Inform user: "Open `cluster-map.html` in a browser to explore the interactive cluster map."

---

## Strategy Import

When invoked with `--from strategy`:

1. Look for the most recent `duckwork-seo:seo-plan` output in the current directory (search for
   files matching `*SEO*Plan*`, `*strategy*`, `*content-strategy*`)
2. Parse markdown tables for: keywords, page types, content pillars, URL structures
3. Validate extracted data: check for duplicates, missing keywords, incomplete entries
4. Enrich with SERP data: run SERP overlap analysis on extracted keywords
5. Build cluster plan using the imported keywords as the starting set (skip Step 1)

If no strategy file is found, prompt the user: "No existing SEO plan found in the
current directory. Run `duckwork-seo:seo-plan` first, or provide a seed keyword for fresh clustering."

---

## Execution Workflow

When `duckwork-seo:seo-cluster execute` is invoked:

### Check for a compatible writing skill

Use Duckwork `skills_list` to discover whether a blog-writing or long-form content skill is available. If one is available, load it with `skill_view(name="<exact skill name from skills_list>")` and confirm it supports drafting full articles before using it. The writing skill can be called inline or through `delegate_task`; pass each post's cluster role, keyword, template, word count, internal links, and outline. Execute in priority order: pillar first, then spokes by volume (highest first). After each post is written, scan previous posts for backward-link placeholders and inject the new post's URL. After all posts are written, generate the cluster scorecard.

If no compatible writing skill is available, continue with the workflow below and produce complete content briefs. Do not check Claude-specific directories or assume a writing skill is installed.

### Brief-only workflow

1. Generate detailed content briefs for each post in the cluster plan.
2. Include in each brief:
   - Title and meta description
   - Primary keyword and secondary keywords
   - Template type and suggested structure (H2/H3 outline)
   - Word count target
   - Internal links to include (with anchor text)
   - Key points to cover
   - Competing pages to differentiate from
3. Use `write_file` to save briefs in `cluster-briefs/` as individual Markdown files.
4. Tell the user that the briefs are ready and that a compatible writing skill can be installed or enabled later for article drafting.

---

## Cluster Scorecard

Post-execution quality report. Run automatically after `duckwork-seo:seo-cluster execute` or
on demand via analysis of the output directory.

| Metric | Target | How Measured |
|--------|--------|-------------|
| Coverage | 100% | Posts written / posts planned |
| Link Density | 3+ per post | Count internal links per post |
| Orphan Pages | 0 | Posts with < 1 incoming link |
| Cannibalization | 0 conflicts | Check for duplicate primary keywords |
| Image Count | 1+ per post | Posts with at least one image |
| Pillar Links | 100% | All spokes link to pillar and vice versa |
| Cross-Links | 80%+ | Recommended spoke-to-spoke links implemented |
| Content Gaps | 0 | Planned posts that were skipped or incomplete |

---

## Map Regeneration

When `duckwork-seo:seo-cluster map` is invoked:

1. read_file `cluster-plan.json` from the current directory
2. Scan output directory and update post statuses (planned vs written)
3. Regenerate `cluster-map.html` with updated statuses
4. Report: posts written vs planned, link completion percentage

---

## Output Files

All outputs are written to the current working directory:

| File | Description |
|------|-------------|
| `cluster-plan.json` | Machine-readable cluster plan (full data) |
| `cluster-plan.md` | Human-readable cluster plan summary |
| `cluster-map.html` | Interactive SVG visualization |
| `cluster-briefs/` | Content briefs (if no compatible writing skill) |
| `cluster-scorecard.md` | Post-execution quality report |

---

## Cross-Skill Integration

| Skill | Relationship |
|-------|-------------|
| `seo-plan` | Import source: strategy import reads seo-plan output |
| `seo-content` | Quality check: E-E-A-T validation of generated content |
| `seo-schema` | Schema markup: Article, BreadcrumbList, ItemList for cluster pages |
| `seo-dataforseo` | Data source: SERP data when DataForSEO MCP is available |
| `seo-google` | Reporting: generate PDF report of cluster plan and scorecard |

After cluster planning or execution completes, offer:
"Generate a PDF report? Use `duckwork-seo:seo-google report`"

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "No seed keyword provided" | Missing argument | Prompt user for seed keyword or URL |
| "Insufficient keyword variants" | Expansion yielded < 15 keywords | Run second expansion pass with PAA questions |
| "SERP data unavailable" | web_search and DataForSEO both failing | Retry after 30s; if persistent, use intent-only clustering with warning |
| "No strategy file found" | `--from strategy` but no plan exists | Prompt user to run `duckwork-seo:seo-plan` first |
| "cluster-plan.json not found" | Execute without planning | Prompt user to run `duckwork-seo:seo-cluster plan` first |
| "No compatible writing skill available" | Execute attempted without a blog-writing skill | Generate content briefs instead; explain that a compatible writing skill can be enabled later |
| "DataForSEO budget exceeded" | Cost check returned "blocked" | Fall back to web_search; inform user |
| "Duplicate primary keywords" | Cannibalization detected | Merge affected posts or reassign keywords |
| "Orphan page detected" | Post missing incoming links | Add links from nearest cluster siblings |
| "Resume state corrupted" | Mismatch between plan and output | Rebuild state from output directory scan |

---

## Security

- All URLs fetched via `duckwork seo run render_page.py <url> --mode auto` (SPA-aware SSRF protection via `url_safety`)
- No credentials stored or transmitted
- Output files contain no PII or API keys
- DataForSEO cost checks run before every API call

## FLOW Framework Integration

For prompt-guided keyword research and gap analysis, use `duckwork-seo:seo-flow find [url|topic]`: FLOW's 5 find-stage prompts complement the SERP-overlap clustering methodology with structured discovery prompts.
