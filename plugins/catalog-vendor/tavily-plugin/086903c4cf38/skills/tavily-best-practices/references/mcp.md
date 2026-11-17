# Operate the Duckwork MCP connection

The plugin uses Tavily's hosted `tavily` MCP server. Duckwork owns transport,
schema discovery, credential scope, and OAuth token storage/refresh. No
separate Tavily client installation or authentication session is needed.

## Connection prerequisites

Follow the repository README in the same Duckwork profile used for chat.
OAuth is the recommended interactive method; the API-key connection is an
alternative for automation or a specific project key. Select one complete
connection configuration. The packaged API-key fallback must not leave a
static Authorization header on the native OAuth connection.

Keep the configured `X-Client-Name: duckwork plugin` attribution header. Do not
put credentials in URLs, chat, tool arguments, or generated artifacts.
Never read credential stores or ask the model to manage token files.

Plugin enablement and MCP connection availability are separate checks. An
independently configured server can work while a disabled plugin's skills are
absent. After installation/enablement, start a fresh session, use `skills_list`
to discover qualified names, and load the required skill with `skill_view`.

If Duckwork reports that its MCP SDK or HTTP transport is unavailable, the host
needs its MCP optional feature installed using that Duckwork version's supported
procedure. Do not install a separate Tavily client as a workaround.

## Use the live interface

Duckwork discovers `mcp__tavily__tavily_search`, `mcp__tavily__tavily_extract`,
`mcp__tavily__tavily_map`, `mcp__tavily__tavily_crawl`, and
`mcp__tavily__tavily_research`. Inspect the advertised arguments when needed.
Hosted schema changes are independent of this pinned Markdown bundle.

Use only supported parameters and types. A missing requirement must be reported
explicitly, not silently replaced by a different filter. Do not check login
or connectivity before every otherwise normal tool call.

## Failure handling

| Failure | Response |
| --- | --- |
| OAuth authentication rejected | Report it; direct the user to `duckwork mcp login tavily` in the active profile. |
| API-key authentication rejected | Direct the user to that profile's API-key settings; never request the key in chat. |
| Browser authorization needed in unattended work | Stop and report that an interactive login is required. |
| Rate or credit limit | Stop without automatic retry; count the failed attempt. |
| Partial page failures | Name the missing evidence; keep usable results and avoid pretending full coverage. |
| Timeout | Report unknown completion and preserve a request ID; do not assume cancellation or resubmit a paid task. |

Inspect payload-level errors as well as transport errors. HTTP 200 can contain
a failed tool result. Empty content is not a successful evidence check.
Record tool names, attempt counts, request IDs, and source URLs as appropriate;
never log bearer tokens. Outgoing attribution and production analytics ingestion
are separate verification claims.
