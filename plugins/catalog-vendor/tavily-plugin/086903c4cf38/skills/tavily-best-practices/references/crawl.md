# Map and Crawl through MCP

Use `mcp__tavily__tavily_map` for URL discovery without page-body extraction.
Use `mcp__tavily__tavily_crawl` when the task needs content from a bounded site
section. For only a few selected pages, Map followed by Extract is often enough.

## Map before collecting

Call `mcp__tavily__tavily_map` with:

```json
{
  "url": "https://docs.tavily.com",
  "instructions": "Find MCP authentication documentation",
  "max_depth": 1,
  "max_breadth": 5,
  "limit": 5,
  "allow_external": false
}
```

Inspect the discovered URLs before choosing pages. A bounded map is a sample
of discovered paths, not proof of a complete site inventory or page content.

## Bound the crawl

Call `mcp__tavily__tavily_crawl` with:

```json
{
  "url": "https://docs.tavily.com",
  "instructions": "Find MCP documentation",
  "max_depth": 1,
  "max_breadth": 3,
  "limit": 3,
  "allow_external": false,
  "extract_depth": "basic",
  "format": "markdown"
}
```

Set depth, breadth, and total URL-processing limits explicitly. Increase them
only when the task requires it and the user's budget allows it. Use
`extract_depth=advanced` for extraction complexity, not as a substitute for
choosing relevant pages.

## Scope controls

`select_paths` and `select_domains` are arrays of regular expressions, not
comma-separated domains or shell globs. Test the intended scope on a small
request. `instructions` guides relevant page selection; it does not guarantee
a chunk count, exact output size, or complete coverage.

`allow_external` controls external links in the results. Do not treat it as a
security boundary or a guarantee about every URL the service visits. Verify
returned hostnames when the user's evidence corpus is restricted.

Inspect returned URLs, page content, and failures. Report empty collections or
missing sections. Returned data is not automatically saved as files; use the
normal Duckwork file workflow only if saving is requested. Stop on rate/credit
errors, count failed attempts, and preserve available request IDs.
