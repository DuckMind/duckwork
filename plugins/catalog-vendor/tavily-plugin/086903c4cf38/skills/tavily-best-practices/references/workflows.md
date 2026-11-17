# Compose bounded MCP workflows

Use only the retrieval steps the user's task needs. Plan the allowed request
count before a multi-step workflow and include failures in that count. Stop
on rate/credit errors; do not launch fallback searches that exceed the budget.

## Search, select, extract

1. Use `mcp__tavily__tavily_search` with a concise query, small `max_results`,
   and the requested domain/date controls from the connected schema.
2. Inspect titles, snippets, URLs, and relevance scores. Check the actual
   hostname and the exact entity or project before selecting sources.
3. Use `mcp__tavily__tavily_extract` for selected URLs whose bodies are needed.
   Add a focused `query` when relevant, without inventing chunk-count controls.
4. Inspect successful and failed extractions. Keep each finding tied to its
   source URL and distinguish snippet-only evidence from extracted content.
5. Answer with citations and disclose evidence gaps.

## Map, select, extract or crawl

1. For a known site with unknown paths, use `mcp__tavily__tavily_map` with
   conservative depth, breadth, and total URL-processing limits.
2. For a few relevant pages, call `mcp__tavily__tavily_extract` on those URLs.
   For a site section that genuinely needs many pages, use a bounded
   `mcp__tavily__tavily_crawl` with explicit scope and limits.
3. Verify returned hostnames, usable page content, and incomplete sections.
   Do not describe a capped collection as exhaustive.

## Multi-source research

Use `mcp__tavily__tavily_research` when the user needs a synthesized report
across subtopics. Include scope and desired sources in `input`, choose a model
that fits the task, and allow the configured deadline. Inspect the returned
report and citations. Do not start a duplicate task after an uncertain timeout.

## Keep output manageable

Choose small result/page counts and extract only relevant URLs. Avoid raw
content in Search when snippets are enough. Do not claim that this MCP
connection saves responses to disk before the model sees them or provides
the separate context-isolation workflow of another interface.

If the user requests saved evidence, use the available Duckwork file tools under
their normal approvals, preserving URLs and incomplete-result notes. MCP data
is not automatically an indexed corpus or a persisted artifact.

## Completion check

Check the actual tool outputs before reporting completion. A fluent answer,
successful connection, or HTTP status alone does not prove useful evidence.
Identify empty results, page failures, incomplete research, and unsupported
requirements. Cite sources that support the answer and preserve returned
request IDs when useful for diagnosis.
