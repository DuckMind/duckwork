# Search through MCP

Use `mcp__tavily__tavily_search` to discover sources. Keep queries concise,
usually under 400 characters, and split a complex question only when the
user's request budget permits multiple searches.

## Depth and result size

| `search_depth` | Choose when |
| --- | --- |
| `basic` | A general lookup; this is the default. |
| `advanced` | More thorough retrieval is needed. |
| `fast` | Low latency and relevance both matter. |
| `ultra-fast` | Latency is the priority. |

Use a small explicit `max_results`. Keep `include_raw_content` false unless
full content is needed now; selected results can be extracted afterward.
The current MCP input is a boolean, not a Markdown/text format string.

## Source and date controls

Call `mcp__tavily__tavily_search` with:

```json
{
  "query": "Tavily MCP OAuth",
  "include_domains": ["docs.tavily.com"],
  "max_results": 3,
  "search_depth": "basic",
  "topic": "general"
}
```

- `include_domains` and `exclude_domains` are arrays of domain names. Check
  actual returned hostnames before accepting a restricted corpus.
- `time_range` accepts `day`, `week`, `month`, or `year`. For an explicit
  period, use `start_date` and `end_date` in `YYYY-MM-DD` format. Resolve
  relative dates against the current date and preserve the user's intent.
- `country` is a full country name and only applies to `topic=general`.
  It boosts geographic relevance; it does not prove a source's location.
- Use `general` for mixed topics and current events; select `news` when the
  user explicitly asks for news coverage.
- Only add other options, such as `exact_match` or image metadata, if they are
  in the connected schema and help answer the request.

## Inspect and verify

Read titles, URLs, snippets, and relevance scores. Scores measure relevance to
the query; they do not verify identity, domain eligibility, or factual accuracy.
For similarly named organizations, releases, or versions, confirm the exact
primary source. Extract the strongest selected pages when snippets are insufficient.

Preserve source URLs, returned request IDs, and the distinction between snippet
evidence and verified page content. Empty results do not prove that no source
exists. Count failed attempts toward the user's limit and stop on rate/credit
errors without automatic retries.
