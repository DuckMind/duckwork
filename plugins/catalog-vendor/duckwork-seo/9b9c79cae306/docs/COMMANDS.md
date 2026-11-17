# Commands and skills

Duckwork SEO has two interfaces: Duckwork skills for model-guided SEO workflows, and the `duckwork seo` CLI for controlled execution of bundled scripts.

## Runtime CLI

```bash
duckwork seo setup             # create/refresh the private Python environment
duckwork seo doctor --json     # read-only runtime readiness check
duckwork seo run fetch_page.py https://example.com --json
```

Run scripts only as `duckwork seo run <script.py> [args...]`. The launcher uses the isolated runtime and rejects scripts outside its allowlist. Do not invoke copied Python files directly. Setup downloads pinned packages and, when requested by the runtime, Chromium; it may use substantial disk space.

`fetch_page.py` supports raw fetching by default and rendered fetching with `--render auto|always`; `--max-text N` caps returned text fields. `--json --output page.html` writes successful HTML while keeping the structured result on stdout. Consult `duckwork seo run fetch_page.py --help` for the installed version's options.

## Skills

Use Duckwork `skills_list` to discover the registered `duckwork-seo:*` skills and `skill_view` to load one. Ask Duckwork to run the workflow in natural language; do not type a skill name as a terminal command. The `duckwork-seo:seo` skill routes requests to the matching workflow. Specialist role skills are intended for delegation through Duckwork `delegate_task`, with relevant evidence and a goal in the task context.

Core workflows include site audits, page and technical analysis, content and schema review, GEO, images, sitemap, strategy, international SEO, programmatic SEO, local SEO, backlinks, clustering, drift monitoring, ecommerce, and FLOW. Skill output and external data availability depend on the loaded workflow and configured tools.

## Optional providers

Provider workflows need a compatible Duckwork MCP server or provider credentials. The extension notes describe retained capabilities and limitations; configure each server and secret in Duckwork using the provider's current documentation. A skill's presence does not mean its provider is connected. Do not run paid or externally mutating operations without approval for that operation.
