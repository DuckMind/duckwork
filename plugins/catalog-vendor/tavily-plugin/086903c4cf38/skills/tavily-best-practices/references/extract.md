# Extract through MCP

Use `mcp__tavily__tavily_extract` when the relevant URLs are already known or
have been selected from Search or Map. Select a small relevant set before
fetching page bodies, and verify each hostname against any source restriction.

## Focused extraction

Call `mcp__tavily__tavily_extract` with:

```json
{
  "urls": ["https://docs.tavily.com/documentation/mcp"],
  "query": "OAuth authentication",
  "extract_depth": "basic",
  "format": "markdown"
}
```

`urls` is an array. Use `query` to rerank content chunks by relevance.
`extract_depth` is `basic` or `advanced`; the latter is useful for tables,
embedded content, or pages where basic extraction is insufficient, and can
increase latency. `format` is `markdown` or `text`. Image and favicon options
should be enabled only when needed and supported by the connected schema.

Do not add chunk-count or timeout arguments that the live tool does not expose.
Query relevance does not guarantee a specific response length. Narrow the URL
set when output would be too large, rather than promising file-based context
isolation or silently truncating away evidence.

## Partial failures

Inspect both successful results and `failed_results` when present. A successful
HTTP status does not establish that every URL returned useful content. Identify
which requested pages succeeded, failed, or returned empty content before synthesis.

Do not retry rate/credit errors. For an ordinary page-specific extraction
failure, consider a single advanced extraction only if it fits the remaining
user budget and addresses the reported failure. Count both attempts and retain
the original failure. Never keep increasing depth without a reason.

## Evidence quality

Keep each page URL beside its content. Cite the original page for claims
supported by extraction. If only a search snippet was available, label that
limitation. For identity-sensitive facts, verify the exact organization, person,
project, date, or version rather than relying on a similar page title.
