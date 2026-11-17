# Research through MCP

Use `mcp__tavily__tavily_research` for multi-source synthesis. Prefer Search
and selected Extract calls for a quick fact or a narrow question already
answered by a few sources. Research may take minutes and consume more credits.

## Describe the task

Include the question, known context, timeframe, geography, allowed source
types, and desired report structure in `input`. Share what is already known
so research does not repeat it. Keep directions consistent and avoid adding
unnecessary subtopics.

Call `mcp__tavily__tavily_research` with:

```json
{
  "input": "Explain what IANA reserves example domains for. Use IANA sources and provide a concise report with citations and any limitations.",
  "model": "mini"
}
```

| `model` | Choose when |
| --- | --- |
| `mini` | A narrow task with few subtopics. |
| `pro` | A broad task with many subtopics. |
| `auto` | Task complexity is uncertain. |

The captured MCP schema exposes `input` and `model`. A desired output format
or source restriction in `input` is guidance; verify the result against it.
Do not add streaming, citation-format, or structured-output arguments unless
the live schema exposes them. A request for a JSON report is not a validated
output-schema guarantee.

## Long-running calls

Use the connection's configured research deadline, documented in the repository
README. Submit one task and allow it to finish. Do not invent a separate polling
or status tool when none is advertised.

If the client times out, retain the request ID if available and report that
completion is unknown. A timeout does not prove cancellation. Do not automatically
resubmit the task or claim its result was retrieved. Stop on rate/credit errors
and count every attempt against the user's request limit.

## Verify the report

Check tool errors, any returned completion status, nonempty report content,
and citations. Ensure the findings address the requested scope and cite the
right organizations and dates. Identify missing evidence and disagreements.
If the response is only pending or incomplete, report that state rather than
presenting it as a completed report. Preserve request IDs for diagnosis and
never include credentials in the report.
